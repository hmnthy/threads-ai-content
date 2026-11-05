"""RQ-01 — topic và kết luận so sánh topic có bền qua các lần gom cụm lại không (ADR-0036).

Thiết kế, ngưỡng và ca biên chốt TRƯỚC khi chạy: `docs/rq/RQ-01-seed-stability.md`. Hằng số + luật:
`src/analysis/topic_stability.py`. Script này chỉ điều phối I/O và tính số mô tả; không có tham số
dòng lệnh nào đổi được phương pháp (K, ngưỡng, mức bỏ bài, mốc Jaccard, số hoán vị).

Ba bước, cùng `--out-dir` (mặc định `data/experiments/rq01/`, gitignored — kết quả thô chứa id bài):
1. `freeze` (Windows): sao nhất quán DB thật (`make_copy` của bước publish, an toàn khi job đang
   ghi) → `threads_frozen.db` + `manifest.json` (SHA-256, id lần gom cụm tham chiếu, mốc snapshot).
   Tách khỏi bước WSL2 vì khoá SQLite qua `/mnt/c` không đáng tin khi Windows đang ghi.
     uv run python -m scripts.rq01_seed_stability freeze --source <thư mục chính>/data/threads.db
2. `replicates` (WSL2 — UMAP/HDBSCAN bị Smart App Control chặn trên Windows): kiểm tái lập seed
   tham chiếu (seed + thứ tự job phải ra đúng `labels_json`; lệch → dừng, không chạy tiếp), rồi
   2 nhánh × K lần gọi đúng `cluster_embeddings()` → `reproducibility.json` + `replicates.jsonl`,
   rồi AMI / ARI (so tham chiếu + theo cặp) → `agreement.json` — ở đây vì scikit-learn chỉ được
   import ở bước WSL2. Chạy lại được giữa chừng (bỏ qua lần đã ghi — mỗi lần tất định); dòng gom
   bằng phiên bản thư viện khác → dừng. `--check-only`: chỉ kiểm tái lập.
     wsl -d Ubuntu -- bash -c "cd <repo WSL> && source ~/threads-clustering-env/bin/activate \\
       && python3 -m scripts.rq01_seed_stability replicates"
3. `evaluate` (Windows): `compare_topics()` y như job trên lần tham chiếu và mọi lần xáo trộn
   (`comparisons.jsonl`, chạy lại được giữa chừng; `--workers` chạy song song — mỗi phép so có seed
   cố định nên số không đổi theo số worker), rồi mọi số của pre-registration → `evaluation.json`.
     uv run python -m scripts.rq01_seed_stability evaluate --workers 8
   Không import scikit-learn / UMAP / HDBSCAN. Bộ nhớ đệm phép so khoá theo bản đóng băng + số
   hoán vị + hash code của engine so sánh + phiên bản thư viện + nhãn của chính lần đó.
4. `report`: đọc kết quả đã có (không tính lại phép so) → `report.json` — các số dẫn xuất mà mục
   Kết quả của RQ trích, kể cả phần thăm dò sau khi xem số (gắn nhãn, không thuộc luật).
     uv run python -m scripts.rq01_seed_stability report

Không truyền `--out-dir` thì 3 bước phải chạy từ CÙNG một checkout: `data/` của mỗi worktree là bản
riêng. Mỗi file `.jsonl` chỉ bước tạo ra nó được sửa (cắt dòng ghi dở); bước khác chỉ đọc.
Danh tính code = hash nội dung mọi file trong đồ thị import của điểm vào (`REPLICATE_CODE` = file
này, `COMPARE_CODE` = engine so sánh). Sửa BẤT KỲ file nào trong đồ thị của file này (kể cả phần
in) → chuyển `replicates.jsonl` đi rồi chạy lại `replicates` (đo 2026-11-04: ~0,12 giây mỗi lần
gom cụm sau lần biên dịch đầu, cộng AMI theo cặp); nhãn tất định nên phép so đã lưu vẫn dùng lại
được, trừ khi chính engine so sánh đổi.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import platform
import sqlite3
import struct
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

from src.analysis.significance import DEFAULT_N_PERMUTATIONS
from src.analysis.stats import DistributionStats, distribution_stats
from src.analysis.topic_comparison import (
    COMPARISON_SEED,
    CONCLUSION_ALPHA,
    METRICS,
    UnitObservation,
    compare_topics,
)
from src.analysis.topic_stability import (
    ARMS,
    DIRECTIONS,
    DROP_PERCENT,
    KEEP_PERCENT,
    MATCH_JACCARD,
    NOISE,
    SENSITIVITY_PERCENTS,
    STABILITY_REPLICATES,
    Verdict,
    co_cluster_core,
    comparison_verdict,
    held,
    match_reference_topics,
    n_dropped,
    passes_at,
    passes_rule,
    replicate_positions,
    wilson_interval,
)
from src.db.schema import connect_readonly, latest_cluster_run, latest_snapshot_time
from src.nlp.topic_profile import adjusted_rand_index
from src.pipeline.compare_topics import load_observations

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "experiments" / "rq01"
FROZEN_DB = "threads_frozen.db"
MANIFEST = "manifest.json"
REPRODUCIBILITY = "reproducibility.json"
REPLICATES = "replicates.jsonl"
AGREEMENT = "agreement.json"
COMPARISONS = "comparisons.jsonl"
EVALUATION = "evaluation.json"
# Tham số gom cụm lưu trong `cluster_runs.params_json` phải trùng hằng số production hiện tại —
# RQ giữ nguyên tham số; lần tham chiếu gom bằng tham số khác thì không so được
CLUSTER_PARAMS = (
    "umap_n_components",
    "umap_n_neighbors",
    "hdbscan_min_cluster_size",
    "cluster_selection_method",
)
VERSIONED_PACKAGES = (
    "umap-learn",
    "hdbscan",
    "scikit-learn",
    "numpy",
    "scipy",
    "numba",
    "pynndescent",
)
# Danh tính code của từng bước = SHA-256 nội dung MỌI file `src/` + `scripts/` mà điểm vào import
# (kể cả gián tiếp — dò bằng `ast`, không viết tay danh sách: danh sách tay đã 2 lần thiếu file định
# nghĩa chỉ số). Không dùng git HEAD: trong WSL2 git không đọc được worktree trỏ đường dẫn Windows,
# HEAD bỏ sót sửa chưa commit, và một commit chỉ sửa docs sẽ làm mất cả bộ nhớ đệm. Cùng checkout →
# cùng byte ở cả 2 hệ. Điểm vào của `replicates` là chính file này (bao trọn mọi thứ nó gọi)
REPLICATE_CODE = ("scripts.rq01_seed_stability",)
COMPARE_CODE = ("src.analysis.topic_comparison", "src.pipeline.compare_topics")
_LOCAL_PACKAGES = ("src", "scripts")


class ExperimentError(RuntimeError):
    """Điều kiện của pre-registration không đạt — dừng, không tự sửa (ADR-0036 "Xem lại khi")."""


# --- I/O chung -------------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _open_frozen(out_dir: Path) -> sqlite3.Connection:
    """Bản sao đóng băng không bao giờ đổi → `immutable=1`: SQLite bỏ khoá file (khoá qua `/mnt/c`
    giữa WSL2 và Windows không đáng tin), chỉ đọc."""
    path = (out_dir / FROZEN_DB).resolve()
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentError(
            f"không đọc được {path.name} ({exc}) — chạy lại bước tạo ra nó"
        ) from exc


def _write_json(path: Path, data: Any) -> None:
    """Ghi nguyên tử (file tạm + `os.replace`): máy ngủ giữa chừng không để lại file cụt."""
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _module_file(name: str) -> Path | None:
    base = REPO_ROOT.joinpath(*name.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None  # tên trong module (VD `src.x.HẰNG_SỐ`) hoặc gói ngoài repo


def module_files(entries: Sequence[str]) -> list[str]:
    """File của các module `src.*` / `scripts.*` mà `entries` import, bắc cầu (mọi câu import
    trong file, kể cả trong hàm và dưới `TYPE_CHECKING` — thừa thì chỉ bảo thủ hơn)."""
    seen: set[str] = set()
    files: set[str] = set()
    stack = list(entries)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        path = _module_file(name)
        if path is None:
            continue
        files.add(path.relative_to(REPO_ROOT).as_posix())
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.Import):
                found = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            else:
                continue
            stack.extend(n for n in found if n.split(".")[0] in _LOCAL_PACKAGES)
    return sorted(files)


def code_digest(entries: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for relative in module_files(entries):
        digest.update(relative.encode("utf-8") + b"\0" + (REPO_ROOT / relative).read_bytes())
    return digest.hexdigest()


def read_jsonl(path: Path, *, repair: bool = False) -> list[dict[str, Any]]:
    """Đọc file nối dòng; dòng cuối ghi dở (máy ngủ / tắt giữa chừng, hoặc bước khác đang ghi) bị
    bỏ qua. `repair` — CHỈ bước sở hữu file: cắt dòng dở khỏi file và thêm `\\n` cuối khi thiếu, để
    lần ghi nối sau không dính vào dòng cuối."""
    if not path.exists():
        return []
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    records: list[dict[str, Any]] = []
    good_end = 0  # byte ngay sau dòng hợp lệ cuối cùng
    for index, line in enumerate(lines):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines) - 1:
                raise ExperimentError(f"{path.name}: dòng {index + 1} hỏng giữa file") from None
            break
        good_end += len(line)
    if repair:
        # sửa tại chỗ, không ghi lại cả file: cắt đuôi dở, hoặc thêm `\n` cho dòng cuối hợp lệ
        with path.open("r+b") as f:
            if good_end < len(data):
                f.truncate(good_end)
            elif data and not data.endswith(b"\n"):
                f.seek(0, os.SEEK_END)
                f.write(b"\n")
            f.flush()
            os.fsync(f.fileno())
    return records


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        f.flush()
        os.fsync(f.fileno())


def verified_manifest(out_dir: Path) -> dict[str, Any]:
    """Manifest + kiểm SHA-256 của bản sao đóng băng (bị sửa / thay → dừng)."""
    manifest: dict[str, Any] = _read_json(out_dir / MANIFEST)
    if not isinstance(manifest, dict) or "sha256" not in manifest:
        raise ExperimentError(f"{MANIFEST} không có sha256 — đóng băng lại từ đầu")
    actual = sha256_file(out_dir / FROZEN_DB)
    if actual != manifest["sha256"]:
        raise ExperimentError(
            f"{FROZEN_DB} đã đổi sau khi đóng băng ({actual[:12]} ≠ {manifest['sha256'][:12]})"
        )
    return manifest


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def _versions() -> dict[str, str | None]:
    found: dict[str, str | None] = {"python": platform.python_version()}
    for package in VERSIONED_PACKAGES:
        try:
            found[package] = version(package)
        except PackageNotFoundError:
            found[package] = None
    return found


# --- freeze (Windows) --------------------------------------------------------------------------


def run_freeze(source: Path, out_dir: Path) -> dict[str, Any]:
    """Sao DB thật một lần duy nhất; đã có bản sao → dừng (đóng băng lại = đổi dữ liệu giữa
    chừng)."""
    from src.pipeline.publish import make_copy

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / FROZEN_DB
    if target.exists():
        raise ExperimentError(f"{target} đã có — đóng băng chỉ làm một lần; xoá tay nếu chủ ý")
    make_copy(source, target)
    conn = connect_readonly(target)
    try:
        run = latest_cluster_run(conn)
        if run is None:
            raise ExperimentError("bản sao chưa có lần gom cụm nào")
        snapshot = latest_snapshot_time(conn)
        comparison = conn.execute(
            "SELECT cluster_run_id, snapshot_as_of FROM topic_comparison_runs "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    manifest = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "source": str(source),
        "sha256": sha256_file(target),
        "reference_cluster_run_id": run["id"],
        "reference_run_at": run["run_at"],
        "reference_n_units": run["n_units"],
        "reference_n_clusters": run["n_clusters"],
        "latest_snapshot": snapshot,
        "stored_comparison_run": None if comparison is None else dict(comparison),
        "commit": _git_commit(),
    }
    _write_json(out_dir / MANIFEST, manifest)
    return manifest


# --- replicates (WSL2) ----------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceInputs:
    """Đầu vào đúng như job lúc gom cụm tham chiếu: unit theo thứ tự file export
    (`list_content_units()`, bỏ bài không có chữ, không sắp lại), chỉ unit có trong
    `labels_json`."""

    run_id: int
    params: dict[str, Any]
    labels: dict[str, int]
    order: list[str]
    matrix: np.ndarray
    n_new_units_filtered: int
    n_hash_mismatch: int
    stored_dbcv: float | None


def reference_order(
    units: Iterable[tuple[str, str | None]], labels: Mapping[str, int]
) -> tuple[list[str], int]:
    """(thứ tự job của unit tham chiếu, số unit có chữ mới hơn lần tham chiếu bị lọc ra).
    `units` = (id, full_text) theo thứ tự `list_content_units()`."""
    with_text = [unit for unit, text in units if (text or "").strip()]
    order = [unit for unit in with_text if unit in labels]
    missing = set(labels) - set(order)
    if missing:
        raise ExperimentError(f"{len(missing)} unit của labels_json không còn trong content_units")
    return order, len(with_text) - len(order)


def load_reference_inputs(conn: sqlite3.Connection, run_id: int) -> ReferenceInputs:
    from src.db.schema import content_hash, list_content_units

    run = latest_cluster_run(conn)
    if run is None or run["id"] != run_id:
        raise ExperimentError(f"lần gom cụm mới nhất của bản sao không phải {run_id}")
    labels: dict[str, int] = {u: int(x) for u, x in json.loads(run["labels_json"]).items()}
    rows = list_content_units(conn)
    order, n_new = reference_order(((row["id"], row["full_text"]) for row in rows), labels)
    text_of = {row["id"]: row["full_text"] for row in rows}
    stored: dict[str, tuple[str, bytes, int]] = {
        row["object_id"]: (row["content_hash"], row["vector"], row["dim"])
        for row in conn.execute(
            "SELECT object_id, content_hash, vector, dim FROM embeddings "
            "WHERE object_type = 'content_unit' AND model_id = ?",
            (run["model_id"],),
        )
    }
    absent = [u for u in order if u not in stored]
    if absent:
        raise ExperimentError(f"{len(absent)} unit tham chiếu không có vector đã lưu")
    matrix = np.array([struct.unpack(f"<{stored[u][2]}f", stored[u][1]) for u in order])
    mismatch = sum(1 for u in order if stored[u][0] != content_hash(text_of[u]))
    return ReferenceInputs(
        run_id=run_id,
        params=json.loads(run["params_json"]),
        labels=labels,
        order=order,
        matrix=matrix,
        n_new_units_filtered=n_new,
        n_hash_mismatch=mismatch,
        stored_dbcv=run["dbcv"],
    )


def vector_digest(order: Sequence[str], matrix: np.ndarray) -> str:
    """SHA-256 của (id, vector float32) theo đúng thứ tự đưa vào — ghi lại vector đã dùng."""
    digest = hashlib.sha256()
    for unit, row in zip(order, matrix, strict=True):
        digest.update(unit.encode("utf-8") + b"\0")
        digest.update(np.asarray(row, dtype="<f4").tobytes())
    return digest.hexdigest()


def same_partition(a: Sequence[int], b: Sequence[int]) -> bool:
    """Cùng cách chia, chỉ được khác cách đánh số cụm: song ánh giữa nhãn, unclustered ↔
    unclustered."""
    if len(a) != len(b):
        return False
    forward: dict[int, int] = {}
    backward: dict[int, int] = {}
    for x, y in zip(a, b, strict=True):
        if (x == NOISE) != (y == NOISE):
            return False
        if forward.setdefault(x, y) != y or backward.setdefault(y, x) != x:
            return False
    return True


@dataclass(frozen=True)
class Clustering:
    labels: list[int]
    dbcv: float | None
    dbcv_relative: float | None


Clusterer = Callable[[np.ndarray, int], Clustering]


def production_clusterer(matrix: np.ndarray, umap_seed: int) -> Clustering:
    """Đúng `cluster_embeddings()` + `_dbcv()` của job; seed đổi bằng cách gán
    `UMAP_RANDOM_STATE` (như `scripts/topic_identity_eval.py`), trả lại giá trị cũ sau đó."""
    from src.nlp import topics
    from src.pipeline.cluster_wsl import _dbcv

    previous = topics.UMAP_RANDOM_STATE
    topics.UMAP_RANDOM_STATE = umap_seed
    try:
        result = topics.cluster_embeddings(matrix)
    finally:
        topics.UMAP_RANDOM_STATE = previous
    return Clustering(
        labels=[int(x) for x in result.labels],
        dbcv=_dbcv(result.umap_coords, result.labels),
        dbcv_relative=result.relative_validity,
    )


def _production_params() -> dict[str, Any]:
    from src.nlp import topics

    return {
        "umap_n_components": topics.UMAP_N_COMPONENTS,
        "umap_n_neighbors": topics.UMAP_N_NEIGHBORS,
        "hdbscan_min_cluster_size": topics.HDBSCAN_MIN_CLUSTER_SIZE,
        "cluster_selection_method": topics.CLUSTER_SELECTION_METHOD,
    }


def check_reproducibility(
    out_dir: Path,
    *,
    clusterer: Clusterer = production_clusterer,
    production_params: Mapping[str, Any] | None = None,
) -> tuple[ReferenceInputs, dict[str, Any]]:
    """Seed tham chiếu + thứ tự job + vector đã lưu phải ra đúng `labels_json`. Ghi
    `reproducibility.json` cả khi lệch (kèm phiên bản thư viện để báo Thy), rồi dừng nếu lệch."""
    manifest = verified_manifest(out_dir)
    conn = _open_frozen(out_dir)
    try:
        ref = load_reference_inputs(conn, manifest["reference_cluster_run_id"])
    finally:
        conn.close()
    if not isinstance(ref.params.get("umap_random_state"), int):
        raise ExperimentError(
            "params_json của lần tham chiếu không ghi umap_random_state — báo Thy"
        )
    expected_params = dict(production_params or _production_params())
    params_match = all(ref.params.get(k) == expected_params[k] for k in CLUSTER_PARAMS)
    seed = int(ref.params["umap_random_state"])
    report: dict[str, Any] = {
        "checked_at": datetime.now(UTC).isoformat(),
        "frozen_sha256": manifest["sha256"],
        "reference_cluster_run_id": ref.run_id,
        "n_units": len(ref.order),
        "n_new_units_filtered": ref.n_new_units_filtered,
        "n_vector_hash_mismatch": ref.n_hash_mismatch,
        "vector_sha256": vector_digest(ref.order, ref.matrix),
        "reference_params": ref.params,
        "production_params": expected_params,
        "params_match": params_match,
        "umap_seed": seed,
        "versions": _versions(),
        "commit": _git_commit(),
    }
    if params_match:
        reproduced = clusterer(ref.matrix, seed)
        stored = [ref.labels[u] for u in ref.order]
        report["passed"] = same_partition(stored, reproduced.labels)
        report["identical_numbering"] = stored == reproduced.labels
        report["n_units_label_differs"] = sum(
            1 for x, y in zip(stored, reproduced.labels, strict=True) if x != y
        )
        report["dbcv_stored"] = ref.stored_dbcv
        report["dbcv_reproduced"] = reproduced.dbcv
    else:
        report["passed"] = False
    _write_json(out_dir / REPRODUCIBILITY, report)
    if not params_match:
        raise ExperimentError("tham số của lần tham chiếu khác hằng số production — báo Thy")
    if not report["passed"]:
        raise ExperimentError(
            "kiểm tái lập thất bại: seed tham chiếu + thứ tự job không ra đúng labels_json — "
            "dừng, báo Thy (ADR-0036 Xem lại khi 1); phiên bản thư viện trong reproducibility.json"
        )
    return ref, report


def run_replicates(
    out_dir: Path,
    *,
    clusterer: Clusterer = production_clusterer,
    production_params: Mapping[str, Any] | None = None,
    replicates: int = STABILITY_REPLICATES,
    check_only: bool = False,
    agreement: Callable[[Mapping[str, int], Sequence[Mapping[str, Any]]], Any] | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """`agreement` mặc định = `agreement_summary` (cần scikit-learn — chỉ có nghĩa trong WSL2);
    test truyền hàm thuần Python để bộ test nhanh không import scikit-learn trên Windows."""
    # Kiểm các dòng đã có TRƯỚC khi ghi `reproducibility.json`: lần chạy bị từ chối không được đè
    # báo cáo của lần đã chấp nhận
    manifest = verified_manifest(out_dir)
    path = out_dir / REPLICATES
    existing = read_jsonl(path, repair=True)
    if not all(_same_freeze(r, manifest["sha256"]) for r in existing):
        raise ExperimentError(f"{REPLICATES} có dòng của bản đóng băng khác — chuyển file đi")
    # Chạy tiếp bằng venv khác hoặc code khác: kiểm tái lập vẫn có thể đạt (lần tham chiếu không
    # dùng hoán vị) mà các lần còn lại gom khác → mọi dòng phải cùng phiên bản + cùng code
    if not all(r.get("versions") == _versions() for r in existing):
        raise ExperimentError(f"{REPLICATES} có dòng gom bằng phiên bản thư viện khác — báo Thy")
    code = code_digest(REPLICATE_CODE)
    if not all(r.get("code_sha256") == code for r in existing):
        raise ExperimentError(f"{REPLICATES} có dòng gom bằng code khác — chuyển file đi")
    ref, report = check_reproducibility(
        out_dir, clusterer=clusterer, production_params=production_params
    )
    digest = report["vector_sha256"][:12]
    log(f"tái lập OK: lần {ref.run_id}, {len(ref.order)} unit, vector {digest}")
    if check_only:
        return report
    done = {(r["arm"], r["b"]) for r in existing}
    n = len(ref.order)
    for b in range(1, replicates + 1):
        for arm in ARMS:
            if (arm, b) in done:
                continue
            positions = replicate_positions(n, b, arm)
            order = [ref.order[i] for i in positions]
            started = time.perf_counter()
            result = clusterer(ref.matrix[positions], b)
            labels = dict(zip(order, result.labels, strict=True))
            n_clusters = len({x for x in result.labels if x != NOISE})
            _append_jsonl(
                path,
                {
                    "frozen_sha256": report["frozen_sha256"],
                    "versions": report["versions"],
                    "code_sha256": code,
                    "arm": arm,
                    "b": b,
                    "umap_seed": b,
                    "order": order,
                    "labels": labels,
                    "labels_sha256": labels_digest(labels),
                    "n_clusters": n_clusters,
                    "noise_ratio": result.labels.count(NOISE) / len(result.labels),
                    "dbcv": result.dbcv,
                    "dbcv_relative": result.dbcv_relative,
                    "seconds": round(time.perf_counter() - started, 2),
                },
            )
            log(f"{arm} b={b}: {n_clusters} cụm, {len(order)} unit")
    records = read_jsonl(path)
    _write_json(
        out_dir / AGREEMENT,
        {
            "frozen_sha256": report["frozen_sha256"],
            "versions": report["versions"],
            "code_sha256": code,
            "labels_sha256": {f"{r['arm']}:{r['b']}": r["labels_sha256"] for r in records},
            "arms": (agreement or agreement_summary)(ref.labels, records),
        },
    )
    log(f"AMI / ARI → {AGREEMENT}")
    return report


def _same_freeze(record: Mapping[str, Any], frozen_sha256: str) -> bool:
    return bool(record.get("frozen_sha256") == frozen_sha256)


def labels_digest(labels: Mapping[str, int]) -> str:
    """SHA-256 của (unit, nhãn) theo thứ tự đưa vào — khoá bộ nhớ đệm phép so vào ĐÚNG cách chia
    đó: gom lại ra nhãn khác thì phép so cũ không được dùng lại."""
    return hashlib.sha256(json.dumps(list(labels.items())).encode("utf-8")).hexdigest()


# --- evaluate (Windows) ------------------------------------------------------------------------


def _row_record(row: Any) -> dict[str, Any]:
    return {
        "group_id": row.group_id,
        "metric": row.metric,
        "n": row.group.n,
        "rest_n": None if row.rest is None else row.rest.n,
        "effect_size": row.effect_size,
        "p_value_holm": row.p_value_holm,
        "insufficient_data": row.insufficient_data,
    }


def comparison_rows(
    units: Sequence[UnitObservation], n_permutations: int
) -> tuple[list[dict[str, Any]], int]:
    """`compare_topics()` y như job (seed `COMPARISON_SEED`) → (dòng topic, cỡ họ Holm)."""
    result = compare_topics(units, n_permutations=n_permutations, random_seed=COMPARISON_SEED)
    rows = [_row_record(row) for row in result.rows if row.kind == "topic"]
    return rows, result.holm_family_size


def replicate_units(
    labels: Mapping[str, int], insights: Mapping[str, Any]
) -> list[UnitObservation]:
    """Unit có mặt ở lần b; cụm c → topic "c<nhãn>", unclustered → None (vào phần còn lại)."""
    return [
        UnitObservation(
            unit_id=unit,
            topic_id=None if label == NOISE else f"c{label}",
            insights=insights.get(unit),
        )
        for unit, label in labels.items()
    ]


def compare_code_digest() -> str:
    """Danh tính code của phép so = `COMPARE_CODE` + nguồn của 3 hàm trong file này định nghĩa
    phép so (cách đưa unclustered vào phần còn lại, lọc dòng topic, trường giữ lại). Không lấy cả
    file: sửa phần tóm tắt / in không được làm mất ~1 giờ phép so đã lưu. `_compare_task` chỉ đóng
    gói kết quả của `comparison_rows` nên không tính vào."""
    helpers = "".join(inspect.getsource(f) for f in (_row_record, comparison_rows, replicate_units))
    return hashlib.sha256((code_digest(COMPARE_CODE) + helpers).encode("utf-8")).hexdigest()


def _compare_task(
    task: tuple[str, int, str, list[UnitObservation], int],
) -> dict[str, Any]:
    arm, b, digest, units, n_permutations = task
    started = time.perf_counter()
    rows, family = comparison_rows(units, n_permutations)
    return {
        "arm": arm,
        "b": b,
        "labels_sha256": digest,
        "n_permutations": n_permutations,
        "holm_family_size": family,
        "rows": rows,
        "seconds": round(time.perf_counter() - started, 2),
    }


def run_comparisons(
    out_dir: Path,
    replicate_records: Sequence[Mapping[str, Any]],
    insights: Mapping[str, Any],
    *,
    workers: int,
    n_permutations: int,
    frozen_sha256: str,
    compare_code: str,
    log: Callable[[str], None] = print,
) -> dict[tuple[str, int], dict[str, Any]]:
    """Phép so của mọi lần xáo trộn, ghi nối vào `comparisons.jsonl` (chạy lại thì bỏ lần đã có).
    `compare_code` = `compare_code_digest()` tính MỘT lần đầu `run_evaluate`."""
    path = out_dir / COMPARISONS
    existing = read_jsonl(path, repair=True)
    # Khoá = bản đóng băng + số hoán vị + code của engine + phiên bản thư viện (engine có seed đổi
    # thì mọi p đổi — không trộn 2 engine) + nhãn của chính lần đó
    stamp = {
        "frozen_sha256": frozen_sha256,
        "n_permutations": n_permutations,
        "code_sha256": compare_code,
        "versions": _versions(),
    }
    for record in existing:
        if any(record.get(key) != value for key, value in stamp.items()):
            raise ExperimentError(f"{COMPARISONS} thuộc lần chạy khác — chuyển file đi")
    done = {(r["arm"], r["b"]): r for r in existing}
    for r in replicate_records:
        cached = done.get((r["arm"], r["b"]))
        if cached is not None and cached.get("labels_sha256") != labels_digest(r["labels"]):
            raise ExperimentError(
                f"{COMPARISONS}: phép so {r['arm']} b={r['b']} tính trên nhãn khác — chuyển file đi"
            )
    tasks = [
        (
            r["arm"],
            r["b"],
            labels_digest(r["labels"]),
            replicate_units(r["labels"], insights),
            n_permutations,
        )
        for r in replicate_records
        if (r["arm"], r["b"]) not in done
    ]

    def finished(results: Iterator[dict[str, Any]]) -> None:
        for result in results:
            result.update(stamp)
            _append_jsonl(path, result)
            done[(result["arm"], result["b"])] = result
            log(f"so sánh {result['arm']} b={result['b']}: {result['seconds']} s")

    if workers <= 1:
        finished(_compare_task(task) for task in tasks)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            finished(pool.map(_compare_task, tasks))
    return done


def _stats(values: Sequence[float | None]) -> dict[str, float | int]:
    """median + IQR + n (n = số giá trị có thật; None bị bỏ và đếm riêng)."""
    present = [float(v) for v in values if v is not None]
    stats: DistributionStats = distribution_stats(present)
    return {
        "n": stats.n,
        "n_missing": len(values) - len(present),
        "median": stats.median,
        "iqr_low": stats.iqr_low,
        "iqr_high": stats.iqr_high,
    }


def partition_agreement(a: Mapping[str, int], b: Mapping[str, int]) -> dict[str, float | None]:
    """AMI (chính) + ARI giữa 2 cách chia trên unit chung, 2 cách như `compare_with_previous`:
    (a) unclustered là một nhãn; (b) chỉ unit được gom cụm ở cả hai lần. < 2 unit → None.
    Chỉ gọi ở bước `replicates` (WSL2): scikit-learn chỉ được import ở bước WSL2 (Smart App
    Control chặn phần mở rộng biên dịch trên Windows)."""
    from sklearn.metrics import adjusted_mutual_info_score  # type: ignore[import-untyped]

    common = [u for u in a if u in b]
    both = [u for u in common if a[u] != NOISE and b[u] != NOISE]

    def scores(units: list[str]) -> tuple[float | None, float | None]:
        if len(units) < 2:
            return None, None
        x, y = [a[u] for u in units], [b[u] for u in units]
        ami = float(adjusted_mutual_info_score(x, y, average_method="arithmetic"))
        return ami, adjusted_rand_index(x, y)

    ami_all, ari_all = scores(common)
    ami_clustered, ari_clustered = scores(both)
    return {
        "ami_all": ami_all,
        "ari_all": ari_all,
        "ami_clustered": ami_clustered,
        "ari_clustered": ari_clustered,
    }


_AGREEMENT_KEYS = ("ami_all", "ari_all", "ami_clustered", "ari_clustered")


def agreement_summary(
    reference_labels: Mapping[str, int], replicate_records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Mức cách chia, mỗi nhánh: mỗi lần b so với lần tham chiếu, và mọi cặp lần (b, b′), b < b′
    — median + IQR + n của AMI / ARI theo 2 cách (`partition_agreement`)."""
    result: dict[str, Any] = {}
    for arm in ARMS:
        records = sorted((r for r in replicate_records if r["arm"] == arm), key=lambda r: r["b"])
        vs_reference: dict[str, list[float | None]] = {k: [] for k in _AGREEMENT_KEYS}
        pairwise: dict[str, list[float | None]] = {k: [] for k in _AGREEMENT_KEYS}
        for record in records:
            for key, value in partition_agreement(reference_labels, record["labels"]).items():
                vs_reference[key].append(value)
        for x, y in combinations(records, 2):
            for key, value in partition_agreement(x["labels"], y["labels"]).items():
                pairwise[key].append(value)
        result[arm] = {
            "vs_reference": {k: _stats(v) for k, v in vs_reference.items()},
            "pairwise": {k: _stats(v) for k, v in pairwise.items()},
        }
    return result


def summarise(
    reference_labels: Mapping[str, int],
    reference_topics: Mapping[str, Sequence[str]],
    reference_rows: Sequence[Mapping[str, Any]],
    replicate_records: Sequence[Mapping[str, Any]],
    comparisons: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    replicates: int = STABILITY_REPLICATES,
    agreement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Mọi số của pre-registration từ kết quả thô — hàm thuần (test trên dữ liệu giả). AMI / ARI
    tính sẵn ở bước WSL2 (`agreement_summary`), ghép vào từng nhánh khi có.

    Mẫu số của tỉ lệ giữ luôn là `replicates`: lần thiếu dòng / không cụm khớp / p không xác định
    đều là không giữ."""
    by_arm: dict[str, list[Mapping[str, Any]]] = {arm: [] for arm in ARMS}
    for record in sorted(replicate_records, key=lambda r: (r["arm"], r["b"])):
        by_arm[record["arm"]].append(record)
    for arm in ARMS:
        bs = [r["b"] for r in by_arm[arm]]
        if bs != list(range(1, replicates + 1)):
            raise ExperimentError(f"nhánh {arm}: cần đủ b = 1…{replicates}, có {len(bs)} lần")
        missing = [b for b in bs if (arm, b) not in comparisons]
        if missing:
            raise ExperimentError(f"nhánh {arm}: thiếu phép so ở {len(missing)} lần")

    ref_row = {(r["group_id"], r["metric"]): r for r in reference_rows}
    pairs = [(t, m) for t in sorted(reference_topics) for m in METRICS]
    ref_verdict: dict[tuple[str, str], Verdict] = {key: _verdict(ref_row.get(key)) for key in pairs}

    arms: dict[str, Any] = {}
    for arm in ARMS:
        kept: Counter[tuple[str, str, str]] = Counter()
        matched_verdicts: dict[tuple[str, str], Counter[str]] = {k: Counter() for k in pairs}
        jaccard: dict[str, list[float]] = {t: [] for t in reference_topics}
        alive: Counter[str] = Counter()
        new_conclusions: list[int] = []
        new_unmatched: list[int] = []
        for record in by_arm[arm]:
            labels: Mapping[str, int] = record["labels"]
            rows = {
                (r["group_id"], r["metric"]): r for r in comparisons[(arm, record["b"])]["rows"]
            }
            matches = match_reference_topics(reference_topics, labels)
            for topic, match in matches.items():
                jaccard[topic].append(match.jaccard)
                alive[topic] += match.alive
            for topic, metric in pairs:
                match = matches[topic]
                row = rows.get((f"c{match.cluster}", metric)) if match.alive else None
                matched_verdicts[(topic, metric)][
                    _verdict(row) if match.alive else "topic not found"
                ] += 1
                for direction in DIRECTIONS:
                    if row is not None and held(
                        direction,
                        match,
                        row["p_value_holm"],
                        row["effect_size"],
                        bool(row["insufficient_data"]),
                    ):
                        kept[(topic, metric, direction)] += 1
            matched_clusters = {f"c{m.cluster}" for m in matches.values() if m.alive}
            conclusions = [r for r in rows.values() if _verdict(r) in DIRECTIONS]
            new_conclusions.append(len(conclusions))
            new_unmatched.append(
                sum(1 for r in conclusions if r["group_id"] not in matched_clusters)
            )

        conclusions_out = []
        for topic, metric in pairs:
            entry: dict[str, Any] = {
                "topic": topic,
                "metric": metric,
                "reference_verdict": ref_verdict[(topic, metric)],
                "matched_verdicts": dict(matched_verdicts[(topic, metric)]),
            }
            for direction in DIRECTIONS:
                k = kept[(topic, metric, direction)]
                low, high = wilson_interval(k, replicates)
                entry[direction] = {
                    "kept": k,
                    "rate": k / replicates,
                    "wilson_low": low,
                    "wilson_high": high,
                    "ci_contains_threshold": low <= KEEP_PERCENT / 100 <= high,
                }
            if arm == "P":
                entry["passes_rule"] = any(
                    passes_rule(entry["reference_verdict"], d, entry[d]["kept"], replicates)
                    for d in DIRECTIONS
                )
                entry["sensitivity"] = {
                    str(percent): any(
                        passes_at(
                            entry["reference_verdict"], d, entry[d]["kept"], replicates, percent
                        )
                        for d in DIRECTIONS
                    )
                    for percent in SENSITIVITY_PERCENTS
                }
            conclusions_out.append(entry)

        records = by_arm[arm]
        arms[arm] = {
            "conclusions": conclusions_out,
            "topic_stability": {
                t: {
                    "mean_jaccard": sum(js) / replicates,
                    "alive": alive[t],
                    "n_reference_units": len(reference_topics[t]),
                }
                for t, js in jaccard.items()
            },
            "new_conclusions": _stats([float(x) for x in new_conclusions]),
            "new_conclusions_in_unmatched_clusters": _stats([float(x) for x in new_unmatched]),
            "n_clusters": _stats([float(r["n_clusters"]) for r in records]),
            "noise_ratio": _stats([float(r["noise_ratio"]) for r in records]),
            "dbcv_validity_index": _stats([r["dbcv"] for r in records]),
            "n_units_per_replicate": sorted({len(r["labels"]) for r in records}),
        }
        if agreement is not None:
            arms[arm].update(agreement[arm])

    # Lõi thăm dò: topic có tỉ lệ giữ > 0 ở nhánh P (bất kỳ chỉ số / hướng nào)
    signal_topics = sorted(
        {
            c["topic"]
            for c in arms["P"]["conclusions"]
            if c["higher"]["kept"] > 0 or c["lower"]["kept"] > 0
        }
    )
    p_labels = [r["labels"] for r in by_arm["P"]]
    cores = {}
    for topic in signal_topics:
        core = co_cluster_core(reference_topics[topic], p_labels)
        cores[topic] = {
            "n_reference_units": len(reference_topics[topic]),
            "core_size": len(core),
            "core_units": core,
        }
    return {
        "replicates": replicates,
        "rule": {
            "keep_percent": KEEP_PERCENT,
            "drop_percent": DROP_PERCENT,
            "match_jaccard": MATCH_JACCARD,
            "conclusion_alpha": CONCLUSION_ALPHA,
            "sensitivity_percents": list(SENSITIVITY_PERCENTS),
        },
        "reference": {
            "n_units": len(reference_labels),
            "n_topics": len(reference_topics),
            "n_dropped_arm_p": n_dropped(len(reference_labels)),
            "verdicts": {f"{t}:{m}": v for (t, m), v in ref_verdict.items()},
        },
        "arms": arms,
        "exploratory_cores": cores,
    }


def _verdict(row: Mapping[str, Any] | None) -> Verdict:
    if row is None:
        return "not tested"
    return comparison_verdict(
        row["p_value_holm"], row["effect_size"], bool(row["insufficient_data"])
    )


def stored_comparison_check(
    conn: sqlite3.Connection, run_id: int, recomputed: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Đối chiếu verdict tính lại với `topic_comparisons` đã lưu của lần tham chiếu (tính lúc job
    chạy, có thể trên snapshot cũ hơn) — chỉ để báo cáo, không dùng để kết luận."""
    stored = {
        (row["group_id"], row["metric"]): _verdict(row)
        for row in conn.execute(
            "SELECT group_id, metric, p_value_holm, effect_size, insufficient_data "
            "FROM topic_comparisons WHERE cluster_run_id = ? AND kind = 'topic'",
            (run_id,),
        )
    }
    differs = [
        f"{r['group_id']}:{r['metric']}"
        for r in recomputed
        if stored.get((r["group_id"], r["metric"])) != _verdict(r)
    ]
    return {"n_stored_rows": len(stored), "verdict_differs": differs}


def run_evaluate(
    out_dir: Path,
    *,
    workers: int = 1,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
    replicates: int = STABILITY_REPLICATES,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    manifest = verified_manifest(out_dir)
    report = _read_json(out_dir / REPRODUCIBILITY)
    if not report.get("passed") or report.get("frozen_sha256") != manifest["sha256"]:
        raise ExperimentError("chưa có kiểm tái lập đạt trên đúng bản đóng băng này")
    records = read_jsonl(out_dir / REPLICATES)
    if not all(_same_freeze(r, manifest["sha256"]) for r in records):
        raise ExperimentError(f"{REPLICATES} có dòng của bản đóng băng khác")
    # Mọi lần gom cụm cùng phiên bản thư viện với lần kiểm tái lập đã ghi, và nhãn không bị sửa
    # sau khi ghi
    if not all(r.get("versions") == report["versions"] for r in records):
        raise ExperimentError(f"{REPLICATES} có dòng gom bằng phiên bản khác lần kiểm tái lập")
    if not all(r.get("labels_sha256") == labels_digest(r["labels"]) for r in records):
        raise ExperimentError(f"{REPLICATES} có nhãn bị đổi sau khi ghi")
    # Tính danh tính code MỘT lần đầu bước: file bị sửa trong lúc chạy ~1 giờ thì evaluation.json
    # vẫn ghi đúng code đã tính ra số
    replicate_code = code_digest(REPLICATE_CODE)
    compare_code = compare_code_digest()
    if not all(r.get("code_sha256") == replicate_code for r in records):
        raise ExperimentError(f"{REPLICATES} gom bằng code khác checkout này — chạy lại replicates")
    agreement = _read_json(out_dir / AGREEMENT)
    expected_digests = {f"{r['arm']}:{r['b']}": r["labels_sha256"] for r in records}
    if (
        agreement.get("frozen_sha256") != manifest["sha256"]
        or agreement.get("versions") != report["versions"]
        or agreement.get("code_sha256") != replicate_code
        or agreement.get("labels_sha256") != expected_digests
    ):
        raise ExperimentError(f"{AGREEMENT} không khớp {REPLICATES} — chạy lại bước replicates")
    run_id = manifest["reference_cluster_run_id"]
    conn = _open_frozen(out_dir)
    try:
        run = latest_cluster_run(conn)
        if run is None or run["id"] != run_id:
            raise ExperimentError(f"lần gom cụm mới nhất của bản sao không phải {run_id}")
        labels: dict[str, int] = {u: int(x) for u, x in json.loads(run["labels_json"]).items()}
        observations, snapshot_as_of = load_observations(conn, labels)
        # Topic tham chiếu đọc từ `post_topic_labels`, AMI/ARI từ `labels_json`: 2 nguồn phải là
        # cùng một cách chia (pre-registration: "cách chia tham chiếu = nhãn đã lưu")
        topic_index: dict[str, int] = {}
        from_topics = [
            NOISE if o.topic_id is None else topic_index.setdefault(o.topic_id, len(topic_index))
            for o in observations
        ]
        if not same_partition([labels[o.unit_id] for o in observations], from_topics):
            raise ExperimentError("post_topic_labels và labels_json không cùng một cách chia")
        names = {
            row["id"]: row["label_en"] for row in conn.execute("SELECT id, label_en FROM topics")
        }
        log(f"so sánh tham chiếu (lần {run_id}, {len(observations)} unit)…")
        reference_rows, family = comparison_rows(observations, n_permutations)
        stored_check = stored_comparison_check(conn, run_id, reference_rows)
    finally:
        conn.close()
    reference_topics: dict[str, list[str]] = {}
    for obs in observations:
        if obs.topic_id is not None:
            reference_topics.setdefault(obs.topic_id, []).append(obs.unit_id)
    insights = {obs.unit_id: obs.insights for obs in observations}
    comparisons = run_comparisons(
        out_dir,
        records,
        insights,
        workers=workers,
        n_permutations=n_permutations,
        frozen_sha256=manifest["sha256"],
        compare_code=compare_code,
        log=log,
    )
    summary = summarise(
        labels,
        reference_topics,
        reference_rows,
        records,
        comparisons,
        replicates=replicates,
        agreement=agreement["arms"],
    )
    summary["reference"].update(
        {
            "cluster_run_id": run_id,
            "snapshot_as_of": snapshot_as_of,
            "holm_family_size": family,
            "n_permutations": n_permutations,
            "stored_comparison_check": stored_check,
            "topic_names": {t: names.get(t) for t in reference_topics},
        }
    )
    summary["frozen_sha256"] = manifest["sha256"]
    # Phiên bản của tiến trình đã tính ra từng số: gom cụm + DBCV + AMI/ARI ở WSL2 (`replicates`),
    # phép so ở tiến trình này
    summary["reproducibility"] = {
        k: report.get(k)
        for k in ("vector_sha256", "identical_numbering", "versions", "n_new_units_filtered")
    }
    summary["evaluate_versions"] = {"platform": platform.system(), **_versions()}
    # Dấu code thật sự đã tính ra số (commit bỏ sót sửa chưa commit, và trả None trong WSL2)
    summary["code_sha256"] = {"replicates": replicate_code, "compare": compare_code}
    summary["evaluated_at"] = datetime.now(UTC).isoformat()
    summary["commit"] = _git_commit()
    _write_json(out_dir / EVALUATION, summary)
    return summary


def _fmt(stats: Mapping[str, Any], digits: int = 3) -> str:
    if not stats["n"]:
        return "— (n = 0)"
    return (
        f"{stats['median']:.{digits}f} [{stats['iqr_low']:.{digits}f}, "
        f"{stats['iqr_high']:.{digits}f}] (n = {stats['n']})"
    )


def print_summary(summary: Mapping[str, Any]) -> None:
    ref = summary["reference"]
    names = ref.get("topic_names", {})
    print(
        f"tham chiếu: lần {ref.get('cluster_run_id')}, {ref['n_units']} unit, {ref['n_topics']} "
        f"topic, họ Holm {ref.get('holm_family_size')}, bỏ {ref['n_dropped_arm_p']} bài ở nhánh P"
    )
    for arm, data in summary["arms"].items():
        print(f"\n== nhánh {arm} (K = {summary['replicates']}) ==")
        print(f"số cụm {_fmt(data['n_clusters'], 1)}; unclustered {_fmt(data['noise_ratio'])}")
        print(f"DBCV validity_index {_fmt(data['dbcv_validity_index'])}")
        for key, stats in data["vs_reference"].items():
            pair = data.get("pairwise", {}).get(key)
            print(f"{key}: vs tham chiếu {_fmt(stats)}; theo cặp {_fmt(pair) if pair else '—'}")
        print(
            f"kết luận mỗi lần {_fmt(data['new_conclusions'], 1)}; ở cụm không khớp "
            f"{_fmt(data['new_conclusions_in_unmatched_clusters'], 1)}"
        )
        for topic, s in data["topic_stability"].items():
            print(
                f"  {topic} ({names.get(topic)}): J trung bình {s['mean_jaccard']:.3f}, "
                f"sống {s['alive']}/{summary['replicates']}, {s['n_reference_units']} unit"
            )
        for c in data["conclusions"]:
            hi, lo = c["higher"], c["lower"]
            rule = f" luật={'QUA' if c['passes_rule'] else 'trượt'}" if "passes_rule" in c else ""
            print(
                f"  {c['topic']} {c['metric']}: tham chiếu {c['reference_verdict']}; higher "
                f"{hi['kept']} [{hi['wilson_low']:.2f}, {hi['wilson_high']:.2f}], lower "
                f"{lo['kept']} [{lo['wilson_low']:.2f}, {lo['wilson_high']:.2f}]{rule}"
            )
    for topic, core in summary["exploratory_cores"].items():
        print(f"lõi thăm dò {topic}: {core['core_size']}/{core['n_reference_units']} unit")


# --- report (Windows hoặc WSL2): mọi số dẫn xuất mà mục Kết quả của RQ-01 trích ---------------


def report_numbers(
    reference_labels: Mapping[str, int],
    reference_topics: Mapping[str, Sequence[str]],
    replicate_records: Sequence[Mapping[str, Any]],
    comparisons: Mapping[tuple[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    """Số mà `evaluation.json` không lưu sẵn (hàm thuần, chỉ đọc kết quả đã có): phân phối số kết
    luận mỗi lần, phần ở cụm không khớp, cỡ họ Holm, thời gian mỗi phép so.

    Phần `post_hoc` là THĂM DÒ SAU KHI XEM SỐ, không thuộc pre-registration và không thuộc luật:
    mỗi kết luận (cụm có verdict `higher` / `lower`) được xếp theo topic tham chiếu góp nhiều bài
    nhất vào cụm đó — CHỈ so giữa các topic, bài unclustered ở tham chiếu không được tính khi
    chọn (không có topic nào → "unclustered at reference only"); hoà → id nhỏ nhất, đếm ở
    `n_ties`. Kèm thành phần thật của cụm mỗi lớp (bài của topic chính, bài unclustered ở tham
    chiếu, cỡ cụm) để "nằm ở cụm của X" không bị đọc thành "phần lớn là bài của X"."""
    unit_topic = {u: t for t, members in reference_topics.items() for u in members}
    out: dict[str, Any] = {
        "reference": {
            "n_units": len(reference_labels),
            "n_unclustered": sum(1 for x in reference_labels.values() if x == NOISE),
            "n_topics": len(reference_topics),
        },
        "arms": {},
    }
    for arm in ARMS:
        records = sorted((r for r in replicate_records if r["arm"] == arm), key=lambda r: r["b"])
        per_run: Counter[int] = Counter()
        kinds: Counter[str] = Counter()
        classes: Counter[str] = Counter()
        composition: dict[str, list[tuple[int, int, int]]] = {}
        ties = 0
        unmatched = 0
        deltas: dict[str, list[float]] = {}
        families: list[int] = []
        seconds: list[float] = []
        cluster_seconds = [float(r["seconds"]) for r in records if "seconds" in r]
        for record in records:
            comparison = comparisons[(arm, record["b"])]
            families.append(int(comparison["holm_family_size"]))
            seconds.append(float(comparison["seconds"]))
            labels: Mapping[str, int] = record["labels"]
            matches = match_reference_topics(reference_topics, labels)
            matched = {f"c{m.cluster}" for m in matches.values() if m.alive}
            conclusions = [r for r in comparison["rows"] if _verdict(r) in DIRECTIONS]
            per_run[len(conclusions)] += 1
            for row in conclusions:
                kinds[f"{row['metric']}:{_verdict(row)}"] += 1
                unmatched += row["group_id"] not in matched
                deltas.setdefault(f"{row['metric']}:{_verdict(row)}", []).append(
                    float(row["effect_size"])
                )
                members = [u for u, x in labels.items() if f"c{x}" == row["group_id"]]
                sources = Counter(unit_topic[u] for u in members if u in unit_topic)
                top = max(sorted(sources), key=lambda t: sources[t]) if sources else None
                if sources:
                    best = max(sources.values())
                    ties += sum(1 for n in sources.values() if n == best) > 1
                label = top or "unclustered at reference only"
                classes[label] += 1
                from_unclustered = sum(1 for u in members if u not in unit_topic)
                composition.setdefault(label, []).append(
                    (sources[top] if top else 0, from_unclustered, len(members))
                )
        total = sum(kinds.values())
        out["arms"][arm] = {
            "runs_with_any_conclusion": sum(n for k, n in per_run.items() if k > 0),
            "conclusions_per_run": dict(sorted(per_run.items())),
            "n_conclusions": total,
            "n_in_unmatched_clusters": unmatched,
            "conclusions_by_kind": dict(sorted(kinds.items())),
            "holm_family_range": [min(families), max(families)] if families else None,
            "compare_seconds": _stats(seconds),
            "cluster_seconds": {**_stats(cluster_seconds), "total": sum(cluster_seconds)},
            "post_hoc": {
                "by_main_reference_topic": dict(classes.most_common()),
                "n_ties": ties,
                "composition_by_class": {
                    label: {
                        "n_clusters": len(rows),
                        "units_from_main_topic": _stats([float(a) for a, _, _ in rows]),
                        "units_unclustered_at_reference": _stats([float(b) for _, b, _ in rows]),
                        "cluster_size": _stats([float(c) for _, _, c in rows]),
                        "n_with_any_unclustered_at_reference": sum(1 for _, b, _ in rows if b),
                        "n_more_unclustered_than_main_topic": sum(1 for a, b, _ in rows if b > a),
                        "n_main_topic_at_most_half": sum(1 for a, _, c in rows if 2 * a <= c),
                    }
                    for label, rows in composition.items()
                },
                "effect_size_range_by_kind": {
                    k: [min(v), max(v)] for k, v in sorted(deltas.items())
                },
            },
        }
    return out


def run_report(out_dir: Path, *, replicates: int = STABILITY_REPLICATES) -> dict[str, Any]:
    """Đọc kết quả đã có của lần chạy (không tính lại phép so nào) → `report.json` + in ra. Kiểm
    cùng các dấu nhận diện như `evaluate` (bản đóng băng, đủ lần, nhãn của từng phép so) để không
    ghép nhãn của lần gom cụm này với phép so của lần khác."""
    manifest = verified_manifest(out_dir)
    records = read_jsonl(out_dir / REPLICATES)
    comparisons = {(r["arm"], r["b"]): r for r in read_jsonl(out_dir / COMPARISONS)}
    evaluation = _read_json(out_dir / EVALUATION)
    report = _read_json(out_dir / REPRODUCIBILITY)
    expected = {(arm, b) for arm in ARMS for b in range(1, replicates + 1)}
    if {(r["arm"], r["b"]) for r in records} != expected or set(comparisons) != expected:
        raise ExperimentError(f"cần đủ {len(expected)} lần gom cụm và phép so")
    sha = manifest["sha256"]
    if any(
        part.get("frozen_sha256") != sha
        for part in (evaluation, report, *records, *comparisons.values())
    ):
        raise ExperimentError("kết quả thuộc bản đóng băng khác")
    if any(
        comparisons[(r["arm"], r["b"])].get("labels_sha256") != labels_digest(r["labels"])
        for r in records
    ):
        raise ExperimentError(f"{COMPARISONS} tính trên nhãn khác {REPLICATES} — chạy evaluate")
    conn = _open_frozen(out_dir)
    try:
        run = latest_cluster_run(conn)
        if run is None or run["id"] != manifest["reference_cluster_run_id"]:
            raise ExperimentError("lần gom cụm mới nhất của bản sao không khớp manifest")
        labels: dict[str, int] = {u: int(x) for u, x in json.loads(run["labels_json"]).items()}
        observations, _ = load_observations(conn, labels)
    finally:
        conn.close()
    topics: dict[str, list[str]] = {}
    for obs in observations:
        if obs.topic_id is not None:
            topics.setdefault(obs.topic_id, []).append(obs.unit_id)
    numbers = report_numbers(labels, topics, records, comparisons)
    numbers["frozen_sha256"] = sha
    numbers["evaluation_evaluated_at"] = evaluation.get("evaluated_at")
    numbers["topic_names"] = evaluation["reference"].get("topic_names", {})
    numbers["reference"]["dbcv_stored"] = report.get("dbcv_stored")
    # Cặp có tỉ lệ giữ > 0: phân rã verdict của cụm khớp + tỉ lệ giữ CHỈ trong các lần topic sống
    numbers["matched_verdicts"] = {}
    for arm in ARMS:
        stability = evaluation["arms"][arm]["topic_stability"]
        entries = {}
        for c in evaluation["arms"][arm]["conclusions"]:
            for direction in DIRECTIONS:
                kept = c[direction]["kept"]
                if not kept:
                    continue
                alive = stability[c["topic"]]["alive"]
                low, high = wilson_interval(kept, alive)
                entries[f"{c['topic']}:{c['metric']}:{direction}"] = {
                    "matched_verdicts": c["matched_verdicts"],
                    "kept_given_alive": [kept, alive],
                    "wilson_given_alive": [low, high],
                }
        numbers["matched_verdicts"][arm] = entries
    # Chênh số lần "sống" giữa 2 nhánh (cùng b, chỉ khác d bài bị bỏ)
    gaps = {
        t: evaluation["arms"]["S"]["topic_stability"][t]["alive"] - s["alive"]
        for t, s in evaluation["arms"]["P"]["topic_stability"].items()
    }
    widest = max(sorted(gaps), key=lambda t: abs(gaps[t])) if gaps else None
    numbers["alive_gap_s_minus_p"] = {"by_topic": gaps, "widest": widest}
    # Ước thời gian chạy tuần tự từ chính lần chạy: (K lần × 2 nhánh + tham chiếu) × median
    n_compares = 2 * replicates + 1
    numbers["serial_hours_estimate"] = {
        arm: n_compares * numbers["arms"][arm]["compare_seconds"]["median"] / 3600 for arm in ARMS
    }
    _write_json(out_dir / "report.json", numbers)
    print(json.dumps(numbers, indent=2, ensure_ascii=False))
    return numbers


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("step", choices=["freeze", "replicates", "evaluate", "report"])
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--source", type=Path, help="freeze: DB thật cần đóng băng")
    parser.add_argument("--check-only", action="store_true", help="replicates: chỉ kiểm tái lập")
    parser.add_argument("--workers", type=int, default=1, help="evaluate: số tiến trình song song")
    args = parser.parse_args(argv)
    try:
        if args.step == "freeze":
            if args.source is None:
                parser.error("freeze cần --source")
            print(json.dumps(run_freeze(args.source, args.out_dir), indent=2))
        elif args.step == "replicates":
            run_replicates(args.out_dir, check_only=args.check_only)
        elif args.step == "evaluate":
            print_summary(run_evaluate(args.out_dir, workers=args.workers))
        else:
            run_report(args.out_dir)
    except ExperimentError as exc:
        print(f"DỪNG: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
