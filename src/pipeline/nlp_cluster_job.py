"""Job gom cụm hằng ngày (Task Scheduler 12:30, ADR-0017) — thay launcher .bat cũ (ADR-0013).

3 bước, dừng ngay khi 1 bước lỗi (import không bao giờ chạy trên export hỏng):
1. export (Windows) — `src.pipeline.clustering_export`
2. tách từ cho từ khoá (ADR-0022) + embed + UMAP + HDBSCAN (WSL2) — `src.pipeline.cluster_wsl`
3. import + đặt tên (Windows) — `src.pipeline.clustering_import`

Task Scheduler gọi (không console):
`.venv\\Scripts\\pythonw.exe -m src.pipeline.nlp_cluster_job --log data\\logs\\nlp_cluster_job.log`
Chạy tay: `uv run python -m src.pipeline.nlp_cluster_job`

Bước con chạy bằng `python.exe` (không phải `pythonw`) + `CREATE_NO_WINDOW`: có
stdout thật để ghi vào log, nhưng không mở cửa sổ console nào có thể bị đóng.
Cầu nối WSL2 này bỏ ở Phase C (`docs/roadmap.md`).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

from src.pipeline.job_log import run_job

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = REPO_ROOT / "data" / "logs" / "nlp_cluster_job.log"  # log chuẩn (cron + job_health)
WSL_DISTRO = "Ubuntu"
WSL_VENV = "~/threads-clustering-env"  # xem memory/README WSL2: môi trường ML trong Ubuntu


@dataclass(frozen=True)
class Step:
    name: str
    argv: list[str]


def wsl_path(windows_path: PureWindowsPath | Path) -> str:
    """`C:\\Users\\x` → `/mnt/c/Users/x` (mount mặc định của WSL2)."""
    p = PureWindowsPath(windows_path)
    if not p.drive.endswith(":"):
        raise ValueError(f"cần đường dẫn có ổ đĩa Windows, nhận {windows_path!r}")
    return "/mnt/" + p.drive[0].lower() + "/" + "/".join(p.parts[1:])


def console_python(executable: str) -> str:
    """`pythonw.exe` → `python.exe` cùng thư mục (bước con cần stdout thật)."""
    p = PureWindowsPath(executable)  # không dùng Path: trên Linux (CI) `\` không phải dấu tách
    if p.name.lower() == "pythonw.exe":
        return str(p.with_name("python.exe"))
    return executable


def build_steps(repo: PureWindowsPath | Path, python: str) -> list[Step]:
    wsl_cmd = (
        f"cd {shlex.quote(wsl_path(repo))} && source {WSL_VENV}/bin/activate"
        " && python3 -m src.pipeline.cluster_wsl"
    )
    return [
        Step("export", [python, "-m", "src.pipeline.clustering_export"]),
        Step("cluster_wsl", ["wsl", "-d", WSL_DISTRO, "--", "bash", "-c", wsl_cmd]),
        Step("import", [python, "-m", "src.pipeline.clustering_import"]),
    ]


Runner = Callable[..., "subprocess.CompletedProcess[Any]"]


def run_steps(steps: Sequence[Step], runner: Runner = subprocess.run) -> list[str]:
    """Chạy tuần tự; bước nào exit ≠ 0 → RuntimeError, các bước sau không chạy."""
    # UNBUFFERED: stdout của con ghi vào file sẽ bị đệm theo khối → traceback (stderr) chen
    # trước các dòng print trước nó. WSL_UTF8: lỗi của chính wsl.exe mặc định là UTF-16LE.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "WSL_UTF8": "1"}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    done: list[str] = []
    for step in steps:
        print(f"-- bước {step.name}", flush=True)
        proc = runner(
            step.argv,
            cwd=REPO_ROOT,
            stdout=sys.stdout,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=flags,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"bước {step.name} lỗi (exit {proc.returncode}); dừng job")
        done.append(step.name)
    return done


def _run() -> list[str]:
    # Dựng lệnh TRONG body: lỗi ở đây (VD đường dẫn không phải ổ Windows) cũng vào log + exit 1
    return run_steps(build_steps(REPO_ROOT, console_python(sys.executable)))


def main(argv: Sequence[str] | None = None, status_log: Path | None = LOG_PATH) -> int:
    return run_job("nlp_cluster_job", "NLP recluster job (daily)", _run, argv, status_log)


if __name__ == "__main__":
    sys.exit(main())
