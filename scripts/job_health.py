"""Sức khoẻ 2 cron job — hook đầu phiên gọi (`python -m scripts.job_health`), ADR-0013.

Đo độ tươi từ CHÍNH DỮ LIỆU trong DB (snapshot mới nhất, lần gom cụm mới nhất),
không từ dòng cuối của log: job bị giết giữa chừng không ghi dòng kết thúc, dòng cuối
cũ trông vẫn như "OK" (bài học 2026-10-01: job snapshot hỏng gần 1 ngày mà hook không
báo). Kèm `LastTaskResult` + `LastRunTime` của Task Scheduler để biết nguyên nhân.

Ngưỡng là quy tắc vận hành suy từ lịch chạy, không phải tham số thống kê:
chu kỳ + khoảng ân hạn (job snapshot chạy ~2 phút, job NLP tối đa 30 phút).

Không bao giờ crash: hook đầu phiên phụ thuộc vào output này.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "threads.db"
# Hook SessionStart có timeout 20s (.claude/settings.json) — PowerShell lạnh có thể chậm
# + 3 kết nối sqlite (chờ khoá ≤2s mỗi cái, thường vài ms) + git ≤2s: thường ≪ 10s hook cấp cho
# script này; ca xấu nhất (DB bị khoá suốt cả 3 lần) vượt → hook in "timed out", lần sau thử lại
POWERSHELL_TIMEOUT_S = 6
# Đọc tối đa phần cuối này của log khi tìm lần chạy thành công gần nhất
LOG_TAIL_BYTES = 512_000


@dataclass(frozen=True)
class JobSpec:
    task: str
    label: str
    query: str  # trả 1 timestamp ISO: lần job ghi dữ liệu gần nhất
    max_age: timedelta
    log: str
    job_name: str  # tên `run_logged` ghi trong log


@dataclass(frozen=True)
class TaskInfo:
    result: int
    last_run: datetime | None


JOBS = (
    JobSpec(
        task="ThreadsAI_SnapshotJob_4h",
        label="snapshot",
        query="SELECT MAX(fetched_at) FROM insights_snapshots",
        max_age=timedelta(hours=4 + 1),  # chu kỳ 4h + 1h ân hạn
        log="data/logs/scheduled_job.log",
        job_name="scheduled_job",
    ),
    JobSpec(
        task="ThreadsAI_NLPClusterJob_Daily",
        label="NLP recluster",
        query="SELECT MAX(run_at) FROM cluster_runs",
        max_age=timedelta(hours=24 + 2),  # chu kỳ 24h + 2h ân hạn
        log="data/logs/nlp_cluster_job.log",
        job_name="nlp_cluster_job",
    ),
)

# File trạng thái của bước publish (`src/pipeline/publish.py`, ADR-0025) — chỉ ghi khi tải lên Blob
# thành công, nên mốc trong file cũ đi khi publish lỗi hoặc job bị giết
PUBLISH_STATE = "data/logs/publish_state.json"

# Mốc đổi token Threads (ghi bởi `src/api/auth.record_token_refreshed`, không chứa token). Cảnh
# báo khi còn ≤ 7 ngày (cùng ngưỡng `EXPIRY_WARNING_THRESHOLD` của auth.py) hoặc khi job snapshot
# đã quá hạn đổi 1 ngày mà chưa đổi được (`REFRESH_EVERY` + 1 ngày ân hạn — quy tắc vận hành).
TOKEN_META = "data/cache/.token_meta.json"
TOKEN_WARN_DAYS = 7
# Đổi token lỗi liên tục lâu hơn mức này → WARN, kể cả khi chưa từng đổi thành công. Quy tắc vận
# hành: > 24h (Meta chỉ cho đổi token ≥ 24h tuổi → token mới tạo lỗi "hợp lệ" suốt ngày đầu)
# + 4h chu kỳ job + ân hạn → 48h không báo nhầm ở ngày đầu mà vẫn ≪ 60 ngày sống của token.
TOKEN_FAILING_FOR = timedelta(hours=48)

# Mã kết quả Task Scheduler hay gặp
# (learn.microsoft.com: "Task Scheduler Error and Success Constants")
TASK_RESULT_NAMES = {
    0x0: "OK",
    0x1: "exit 1",
    0x41301: "running",
    0x41303: "has not run yet",
    0x41306: "terminated (time limit or stopped)",
    0xC000013A: "STATUS_CONTROL_C_EXIT — console closed",
}
TASK_RUNNING = 0x41301
TASK_NEVER_RAN = 0x41303
# Không phải lỗi: OK, đang chạy, chưa tới lượt chạy lần đầu
HEALTHY_RESULTS = {0x0, TASK_RUNNING, TASK_NEVER_RAN}


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def latest_write(db_path: Path, query: str) -> datetime | None:
    """Timestamp mới nhất; None nếu chưa có DB/bảng/dòng. Lỗi khác (VD DB bị khoá) → raise."""
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        row = conn.execute(query).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return None  # DB cũ chưa migrate
        raise
    finally:
        conn.close()
    return parse_timestamp(row[0] if row else None)


def parse_task_json(raw: str) -> dict[str, TaskInfo]:
    """Parse output `ConvertTo-Json` của PowerShell. Dữ liệu lạ → bỏ qua mục đó."""
    try:
        data: Any = json.loads(raw or "null")
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):  # 1 task → ConvertTo-Json trả object, không phải mảng
        data = [data]
    if not isinstance(data, list):
        return {}
    out: dict[str, TaskInfo] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        name, result = item.get("n"), item.get("r")
        if not isinstance(name, str) or not isinstance(result, int):
            continue
        # LastTaskResult là uint32 nhưng có thể về dạng int32 âm → chuẩn hoá về 0..2^32-1
        out[name] = TaskInfo(result & 0xFFFFFFFF, parse_timestamp(item.get("t")))
    return out


def task_results() -> dict[str, TaskInfo] | None:
    """Thông tin task ThreadsAI_* — None nếu không đọc được (không phải Windows, timeout…)."""
    if sys.platform != "win32":
        return None
    script = (
        "Get-ScheduledTask -TaskName 'ThreadsAI_*' | ForEach-Object { "
        "$i = $_ | Get-ScheduledTaskInfo; "
        "[pscustomobject]@{n=$_.TaskName; r=$i.LastTaskResult; "
        "t=$(if ($i.LastRunTime) { $i.LastRunTime.ToUniversalTime().ToString('o') })} } "
        "| ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=POWERSHELL_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_task_json(proc.stdout)


def last_success(log_path: Path, job_name: str) -> datetime | None:
    """Giờ KẾT THÚC của lần chạy thành công gần nhất (dòng "<job> xong" do `run_logged` ghi).

    Không dùng timestamp dữ liệu trong DB cho việc này: chính lần chạy lỗi có thể đã kịp
    ghi snapshot trước khi hỏng (VD lỗi ở bước daily views sau đó) — so dữ liệu với giờ bắt
    đầu chạy sẽ báo nhầm "đã làm tươi" mãi (code-reviewer 2026-10-01).
    """
    try:
        with log_path.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - LOG_TAIL_BYTES))
            text = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    pattern = re.compile(rf"^\[[^\]]*? -> ([^\]]+)\] {re.escape(job_name)} xong\b", re.M)
    ends = [ts for m in pattern.finditer(text) if (ts := parse_timestamp(m.group(1)))]
    return max(ends, default=None)


def describe_result(code: int) -> str:
    name = TASK_RESULT_NAMES.get(code)
    return f"0x{code:X}" + (f" ({name})" if name else "")


def assess(
    spec: JobSpec,
    latest: datetime | None,
    now: datetime,
    task: TaskInfo | None,
    last_ok: datetime | None = None,
) -> str:
    """1 dòng trạng thái; bắt đầu bằng "WARN" nếu cần chú ý."""
    result = task.result if task else None
    problems: list[str] = []
    if latest is None:
        age_text = "no data written yet"
        problems.append("no data")
    else:
        age = now - latest
        age_text = f"newest data {age.total_seconds() / 3600:.1f}h old"
        if age > spec.max_age:
            hours = spec.max_age.total_seconds() / 3600
            problems.append(f"stale (> {hours:.0f}h)")
    failed = result is not None and result not in HEALTHY_RESULTS
    result_text = describe_result(result) if result is not None else ""
    # Lần chạy theo lịch lỗi nhưng có 1 lần chạy THÀNH CÔNG kết thúc sau đó (chạy tay) → chỉ
    # ghi chú, không WARN — LastTaskResult giữ nguyên tới lần chạy theo lịch kế tiếp.
    refreshed_since = (
        failed
        and not problems
        and task is not None
        and task.last_run is not None
        and last_ok is not None
        and last_ok > task.last_run
    )
    if failed and not refreshed_since:
        problems.append(f"LastTaskResult {result_text}")
    if not problems:
        note = ""
        if result == TASK_RUNNING:
            note = " — task running now"
        elif refreshed_since:
            note = f" — last scheduled run failed: {result_text}; data refreshed since"
        return f"{spec.label} OK ({age_text}){note}"
    hint = f"see {spec.log}"
    if result == TASK_RUNNING:
        hint = "task running now — wait for it; " + hint
    elif result in HEALTHY_RESULTS and latest is not None:
        hint = "task reports OK — machine asleep/off? " + hint
    return f"WARN {spec.label} `{spec.task}`: {age_text}; " + "; ".join(problems) + f" → {hint}"


@dataclass(frozen=True)
class ComparisonInputs:
    cluster_run_id: int
    computed_at: datetime
    snapshot_as_of: datetime
    newest_snapshot: datetime | None


Lag = tuple[int, int | None]


def comparison_status(db_path: Path) -> tuple[Lag | None, ComparisonInputs | None]:
    """Trạng thái so sánh topic, đọc trong 1 kết nối (hook đầu phiên có ngân sách thời gian):

    - lag: (lần gom cụm mới nhất, lần gom cụm của kết quả so sánh mới nhất) khi 2 số lệch nhau —
      bước `compare` (bước cuối của job NLP, ADR-0023) lỗi hoặc chưa chạy; None khi khớp hoặc
      chưa gom cụm lần nào.
    - inputs: lần so sánh mới nhất tính lúc nào, trên số liệu "tính tới" lúc nào, và snapshot
      mới nhất trong DB; None khi chưa có kết quả hoặc thiếu mốc.

    Bảng chưa có (DB chưa migrate) = chưa có kết quả. Lỗi sqlite khác → raise như `latest_write`.
    """
    if not db_path.exists():
        return None, None
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        latest = _scalar_or_none(conn, "SELECT MAX(id) FROM cluster_runs")
        if latest is None:
            return None, None
        try:
            row = conn.execute(
                "SELECT cluster_run_id, computed_at, snapshot_as_of FROM topic_comparison_runs "
                "ORDER BY cluster_run_id DESC LIMIT 1"
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc):
                raise
            row = None  # DB chưa migrate: bước so sánh chưa từng chạy
        newest = _scalar_or_none(conn, "SELECT MAX(fetched_at) FROM insights_snapshots")
    finally:
        conn.close()
    compared = row[0] if row is not None else None
    lag = None if latest == compared else (latest, compared)
    computed_at = parse_timestamp(row[1]) if row is not None else None
    as_of = parse_timestamp(row[2]) if row is not None else None
    if compared is None or computed_at is None or as_of is None:
        return lag, None
    return lag, ComparisonInputs(compared, computed_at, as_of, parse_timestamp(newest))


def _scalar_or_none(conn: sqlite3.Connection, query: str) -> Any:
    try:
        return conn.execute(query).fetchone()[0]
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return None
        raise


def comparison_lag(db_path: Path) -> Lag | None:
    return comparison_status(db_path)[0]


def comparison_inputs(db_path: Path) -> ComparisonInputs | None:
    return comparison_status(db_path)[1]


def stale_comparison_warning(
    inputs: ComparisonInputs, max_age: timedelta, snapshot_running: bool = False
) -> str | None:
    """Kết quả so sánh topic tính trên số liệu cũ hơn ngưỡng tươi của job snapshot (so với lúc
    tính) → cảnh báo. Dòng "NLP recluster OK" chỉ đo lần gom cụm, không đo số liệu nó dùng.
    Ca thật: 13→16/10/2026 job snapshot hỏng, job NLP vẫn "OK" nhưng tính lại trên số liệu
    12/10; 17/10 hai job chạy bù cùng lúc sau 5 ngày đó, `compare` đọc trước khi snapshot kịp
    commit. Chạy chồng sau 1 lần ngủ ngắn (số liệu cũ < ngưỡng) thì không cảnh báo — kết quả
    vẫn trung thực vì trang ghi mốc `snapshot_as_of`."""
    lag = inputs.computed_at - inputs.snapshot_as_of
    if lag <= max_age:
        return None
    newer = inputs.newest_snapshot is not None and inputs.newest_snapshot > inputs.snapshot_as_of
    if newer:
        action = "newer snapshots exist now — run `uv run python -m src.pipeline.compare_topics`"
    elif snapshot_running:
        action = "the snapshot job is running now — wait for it, then rerun compare_topics"
    else:
        action = "the snapshot job has not written newer data — fix it first"
    as_of = inputs.snapshot_as_of.astimezone(UTC)
    return (
        f"WARN topic comparisons: run {inputs.cluster_run_id} used metrics as of "
        f"{as_of:%Y-%m-%d %H:%M} UTC, {lag.total_seconds() / 3600:.0f}h before "
        f"it was computed; {action}"
    )


def token_status(meta_path: Path, now: datetime) -> str:
    """Hạn token Threads long-lived (job snapshot tự đổi mỗi `REFRESH_EVERY`,
    `src/pipeline/token_refresh.py`). Đọc thẳng file mốc (không import `src.api` — nạp `.env` +
    httpx, chậm hook đầu phiên). Không bao giờ raise; không bao giờ đọc/in token."""
    try:  # lỗi ở module job (VD đang merge dở) không được làm mất cả báo cáo sức khoẻ
        from src.pipeline import token_refresh

        refresh_every = token_refresh.REFRESH_EVERY
    except Exception:
        refresh_every = timedelta(days=7)
    if not meta_path.exists():
        return (
            "Threads token: expiry unknown — not refreshed by the snapshot job yet (needs a token "
            "at least 24h old)"
        )
    try:
        raw: Any = json.loads(meta_path.read_text(encoding="utf-8"))
        issued = parse_timestamp(raw.get("issued_at"))
        expires = parse_timestamp(raw.get("expires_at"))
        first_failed = parse_timestamp(raw.get("first_failed_at"))
        last_error = raw.get("last_error")
    except (OSError, ValueError, AttributeError) as exc:
        return f"WARN Threads token: could not read {TOKEN_META} ({exc})"
    # Đổi lỗi kéo dài — kể cả khi CHƯA từng đổi thành công (không có issued_at)
    failing = None
    if first_failed is not None and now - first_failed > TOKEN_FAILING_FOR:
        hours = (now - first_failed).total_seconds() / 3600
        failing = f"auto-refresh failing for {hours:.0f}h (last error: {last_error})"
    if issued is None:
        if failing:
            return (
                f"WARN Threads token: {failing} — see the 'token refresh:' lines in "
                "data/logs/scheduled_job.log"
            )
        return (
            "Threads token: expiry unknown — not refreshed by the snapshot job yet (needs a token "
            "at least 24h old)"
        )
    expires = expires or issued + timedelta(days=60)  # file cũ chỉ có issued_at
    days_left = (expires - now).total_seconds() / 86400
    expiry = (
        f"expires in {days_left:.0f} days"
        if days_left >= 0
        else f"EXPIRED {-days_left:.0f} days ago"
    )
    text = f"{expiry}, refreshed {(now - issued).days} days ago"
    # hạn gần hết là điều gấp nhất → kiểm trước, kèm chi tiết lỗi đổi nếu có
    if days_left <= TOKEN_WARN_DAYS:
        detail = f"; {failing}" if failing else ""
        return (
            f"WARN Threads token: {text}{detail} — create a new one in the Meta dashboard "
            "(docs/claude/data-model.md, token section) if the job cannot refresh it"
        )
    if failing:
        return (
            f"WARN Threads token: {failing}; {text} — see the 'token refresh:' lines in "
            "data/logs/scheduled_job.log"
        )
    if now - issued > refresh_every + timedelta(days=1):
        return (
            f"WARN Threads token: auto-refresh is failing ({text}) — see the 'token refresh:' "
            "lines in data/logs/scheduled_job.log"
        )
    return f"Threads token OK ({text})"


def publish_configured(env_file: Path) -> bool:
    """`.env` có khoá DB_BLOB_PATH không rỗng — chỉ kiểm có mặt, không bao giờ in giá trị.
    Không bao giờ raise (hook đầu phiên phụ thuộc output này)."""
    try:
        from dotenv import dotenv_values

        return bool((dotenv_values(env_file).get("DB_BLOB_PATH") or "").strip())
    except Exception:
        return False


def publish_status(state_path: Path, now: datetime, max_age: timedelta, configured: bool) -> str:
    """Bản sao DB mà trang công khai đọc (ADR-0025). Cùng ngưỡng tươi với job snapshot (chu kỳ
    4h + 1h ân hạn, quy tắc vận hành): publish chạy ở cuối mỗi job snapshot. Chưa có file trạng
    thái: chưa cấu hình → trung tính; đã cấu hình mà chưa lần nào thành công (VD quên
    `uv sync --frozen`, token sai) → WARN."""
    if not state_path.exists():
        if configured:
            return (
                "WARN published copy: configured but never published successfully — see the "
                "'publish:' lines in data/logs/scheduled_job.log"
            )
        return (
            "published copy: not set up yet (no successful publish; needs DB_BLOB_PATH + "
            "BLOB_READ_WRITE_TOKEN in .env)"
        )
    try:
        data: Any = json.loads(state_path.read_text(encoding="utf-8"))
        published = parse_timestamp(data.get("published_at"))
        data_to = data.get("latest_snapshot_at")
    except (OSError, ValueError, AttributeError) as exc:
        return f"WARN published copy: could not read {PUBLISH_STATE} ({exc})"
    if published is None:
        return f"WARN published copy: no valid published_at in {PUBLISH_STATE}"
    age = max(now - published, timedelta(0))  # đồng hồ lệch → không in "-0.3h ago"
    text = f"published {age.total_seconds() / 3600:.1f}h ago, data to {data_to or 'no snapshots'}"
    if age > max_age:
        hours = max_age.total_seconds() / 3600
        return (
            f"WARN published copy: stale ({text}; > {hours:.0f}h) — the public site shows old "
            f"numbers; see the 'publish:' lines in data/logs/scheduled_job.log"
        )
    return f"published copy OK ({text})"


def report(
    db_path: Path = DB_PATH, now: datetime | None = None, repo: Path = REPO_ROOT
) -> list[str]:
    now = now or datetime.now(UTC)
    tasks = task_results() or {}
    lines: list[str] = []
    for spec in JOBS:
        try:
            latest = latest_write(db_path, spec.query)
        except sqlite3.Error as exc:
            lines.append(f"WARN {spec.label}: could not read DB ({exc}) — retry later")
            continue
        last_ok = last_success(repo / spec.log, spec.job_name)
        lines.append(assess(spec, latest, now, tasks.get(spec.task), last_ok))
    nlp = next(spec for spec in JOBS if spec.job_name == "nlp_cluster_job")
    snapshot = next(spec for spec in JOBS if spec.job_name == "scheduled_job")
    nlp_task, snapshot_task = tasks.get(nlp.task), tasks.get(snapshot.task)
    try:
        lag, inputs = comparison_status(db_path)
    except sqlite3.Error as exc:
        lines.append(f"WARN topic comparisons: could not read DB ({exc}) — retry later")
        lag, inputs = None, None
    if lag is not None:
        # Job NLP đang chạy: bước compare (cuối) chưa tới lượt — không phải lỗi
        if not (nlp_task and nlp_task.result == TASK_RUNNING):
            latest_run, compared = lag
            # Chưa từng có kết quả → landing hiện `next`; có kết quả cũ → API ẩn δ/p (`stale`)
            effect = (
                "no results yet, the landing shows the tests as next"
                if compared is None
                else f"results are for run {compared}, the dashboard hides δ and p"
            )
            lines.append(
                f"WARN topic comparisons: latest cluster run {latest_run}; {effect} — run "
                f"`uv run python -m src.pipeline.compare_topics` (see {nlp.log})"
            )
    elif inputs is not None:
        # Cùng ngưỡng "tươi" với job snapshot (chu kỳ 4h + 1h ân hạn): quy tắc vận hành
        running = snapshot_task is not None and snapshot_task.result == TASK_RUNNING
        warning = stale_comparison_warning(inputs, snapshot.max_age, running)
        if warning:
            lines.append(warning)
    lines.append(
        publish_status(
            repo / PUBLISH_STATE, now, snapshot.max_age, publish_configured(repo / ".env")
        )
    )
    lines.append(token_status(repo / TOKEN_META, now))
    return lines


def main_checkout(repo: Path = REPO_ROOT) -> Path:
    """Thư mục chính (nơi cron chạy + DB thật). Phiên trong worktree (ADR-0019) không có
    `data/threads.db` riêng hoặc chỉ có bản sao cũ → luôn đo sức khoẻ trên thư mục chính."""
    import time

    from scripts.git_hygiene import Git, parse_worktrees

    git = Git(deadline_s=2, start=time.monotonic())
    trees = parse_worktrees(git(repo, "worktree", "list", "--porcelain"))
    return trees[0].path if trees else repo


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    root = main_checkout()
    print("\n".join(report(root / "data" / "threads.db", repo=root)))
