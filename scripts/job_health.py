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
POWERSHELL_TIMEOUT_S = 6  # + 2 truy vấn sqlite (≤2s) < 10s hook cấp cho script này
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
