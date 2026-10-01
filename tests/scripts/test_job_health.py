"""Test sức khoẻ cron job (`scripts/job_health.py`, ADR-0013).

Kịch bản thật 2026-10-01: snapshot mới nhất 17:15 ngày 30/09, task trả 0xC000013A
— hook cũ chỉ in dòng log cuối (trông như OK). Giờ phải ra WARN.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import job_health
from scripts.job_health import TaskInfo

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
SNAPSHOT, NLP = job_health.JOBS


def task(result: int, last_run: datetime | None = None) -> TaskInfo:
    return TaskInfo(result, last_run)


def test_fresh_and_ok() -> None:
    line = job_health.assess(SNAPSHOT, NOW - timedelta(hours=2), NOW, task(0))
    assert line == "snapshot OK (newest data 2.0h old)"


def test_real_failure_2026_10_01_is_flagged() -> None:
    latest = datetime(2026, 9, 30, 15, 17, tzinfo=UTC)
    line = job_health.assess(SNAPSHOT, latest, NOW, task(0xC000013A, NOW - timedelta(hours=1)))
    assert line.startswith("WARN snapshot `ThreadsAI_SnapshotJob_4h`")
    assert "stale (> 5h)" in line
    assert "0xC000013A (STATUS_CONTROL_C_EXIT" in line
    assert "data/logs/scheduled_job.log" in line


def test_failed_run_after_newest_data_warns() -> None:
    # Dữ liệu còn trong ngưỡng nhưng lần chạy theo lịch SAU nó lỗi → WARN
    latest = NOW - timedelta(hours=3)
    line = job_health.assess(SNAPSHOT, latest, NOW, task(1, NOW - timedelta(hours=1)))
    assert line.startswith("WARN") and "LastTaskResult 0x1 (exit 1)" in line
    assert "stale" not in line


def test_failed_run_then_successful_manual_run_is_a_note_not_warn() -> None:
    # Lần 03:24 lỗi 0x41306, chạy tay thành công 13:35 → không WARN dính tới 03:00 hôm sau
    last_run = NOW - timedelta(hours=9)
    ok_end = NOW - timedelta(hours=1)
    line = job_health.assess(NLP, ok_end, NOW, task(0x41306, last_run), last_ok=ok_end)
    assert not line.startswith("WARN")
    assert "last scheduled run failed: 0x41306" in line and "data refreshed since" in line


def test_failing_run_that_wrote_data_itself_still_warns() -> None:
    # Lần chạy lỗi đã kịp ghi snapshot (lỗi ở bước sau) → dữ liệu mới hơn giờ chạy, nhưng
    # KHÔNG có lần chạy thành công nào sau đó → vẫn WARN (code-reviewer 2026-10-01)
    last_run = NOW - timedelta(hours=1)
    written = NOW - timedelta(minutes=58)
    old_ok = NOW - timedelta(hours=5)
    line = job_health.assess(SNAPSHOT, written, NOW, task(1, last_run), last_ok=old_ok)
    assert line.startswith("WARN") and "LastTaskResult 0x1" in line


def test_never_ran_is_not_a_failure() -> None:
    line = job_health.assess(SNAPSHOT, NOW - timedelta(hours=1), NOW, task(0x41303))
    assert line == "snapshot OK (newest data 1.0h old)"


def test_running_task_is_named_even_when_stale() -> None:
    line = job_health.assess(SNAPSHOT, NOW - timedelta(hours=9), NOW, task(0x41301))
    assert line.startswith("WARN") and "task running now" in line


def test_last_success_reads_end_time_of_successful_runs(tmp_path: Path) -> None:
    log = tmp_path / "scheduled_job.log"
    log.write_text(
        "[2026-09-30T15:15:02+00:00 -> 2026-09-30T15:17:05+00:00] scheduled_job xong: {}\n"
        "[2026-10-01T12:04:29+00:00] scheduled_job bắt đầu\n"
        "[2026-10-01T12:04:29+00:00 -> 2026-10-01T12:06:15+00:00] scheduled_job xong (exit 0): {}\n"
        "[2026-10-01T16:00:00+00:00] scheduled_job bắt đầu\n"
        "[2026-10-01T16:00:00+00:00 -> 2026-10-01T16:00:09+00:00] scheduled_job LỖI (exit 1): X\n"
        "[2026-10-01T17:00:00+00:00 -> 2026-10-01T17:01:00+00:00] other_job xong (exit 0): {}\n",
        encoding="utf-8",
    )
    expected = datetime(2026, 10, 1, 12, 6, 15, tzinfo=UTC)
    assert job_health.last_success(log, "scheduled_job") == expected
    assert job_health.last_success(log, "nlp_cluster_job") is None
    assert job_health.last_success(tmp_path / "missing.log", "scheduled_job") is None


def test_failed_result_without_run_time_warns() -> None:
    line = job_health.assess(SNAPSHOT, NOW - timedelta(hours=1), NOW, task(1))
    assert line.startswith("WARN")


def test_stale_with_ok_result_hints_sleep() -> None:
    line = job_health.assess(NLP, NOW - timedelta(hours=30), NOW, task(0))
    assert "stale (> 26h)" in line and "machine asleep/off?" in line


def test_threshold_boundary() -> None:
    assert not job_health.assess(SNAPSHOT, NOW - timedelta(hours=5), NOW, task(0)).startswith(
        "WARN"
    )
    late = NOW - timedelta(hours=5, minutes=1)
    assert job_health.assess(SNAPSHOT, late, NOW, task(0)).startswith("WARN")


def test_running_task_and_unknown_result() -> None:
    fresh = NOW - timedelta(hours=1)
    running = job_health.assess(SNAPSHOT, fresh, NOW, task(0x41301))
    assert running == "snapshot OK (newest data 1.0h old) — task running now"
    assert job_health.assess(SNAPSHOT, fresh, NOW, None) == "snapshot OK (newest data 1.0h old)"
    assert "0x80070002" in job_health.assess(SNAPSHOT, fresh, NOW, task(0x80070002))


def test_no_data() -> None:
    line = job_health.assess(NLP, None, NOW, None)
    assert line.startswith("WARN") and "no data written yet" in line


def test_parse_timestamp() -> None:
    assert job_health.parse_timestamp("2026-10-01T10:00:00") == datetime(
        2026, 10, 1, 10, tzinfo=UTC
    )
    assert job_health.parse_timestamp(None) is None
    assert job_health.parse_timestamp("not a date") is None
    assert job_health.parse_timestamp(42) is None


def test_parse_task_json_shapes() -> None:
    one = '{"n":"ThreadsAI_SnapshotJob_4h","r":0,"t":"2026-10-01T12:11:35.0000000Z"}'
    assert job_health.parse_task_json(one) == {
        "ThreadsAI_SnapshotJob_4h": TaskInfo(0, datetime(2026, 10, 1, 12, 11, 35, tzinfo=UTC))
    }
    many = '[{"n":"A","r":-1073741510,"t":null},{"n":"B","r":null},{"x":1},"junk"]'
    # int32 âm → uint32 (0xC000013A); mục có r=null hoặc sai dạng bị bỏ qua
    assert job_health.parse_task_json(many) == {"A": TaskInfo(0xC000013A, None)}
    for raw in ("", "null", '"str"', "42", "{not json"):
        assert job_health.parse_task_json(raw) == {}


def test_latest_write_reads_db(tmp_path: Path) -> None:
    db = tmp_path / "t #1.db"  # ký tự đặc biệt trong đường dẫn: URI phải được encode
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE insights_snapshots (fetched_at TEXT)")
    conn.executemany(
        "INSERT INTO insights_snapshots VALUES (?)",
        [("2026-09-30T15:17:05+00:00",), ("2026-09-30T11:16:49+00:00",)],
    )
    conn.commit()
    conn.close()
    expected = datetime(2026, 9, 30, 15, 17, 5, tzinfo=UTC)
    assert job_health.latest_write(db, SNAPSHOT.query) == expected
    assert job_health.latest_write(db, NLP.query) is None  # bảng cluster_runs chưa có
    assert job_health.latest_write(tmp_path / "missing.db", SNAPSHOT.query) is None


def test_report_survives_db_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def locked(db_path: Path, query: str) -> datetime | None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(job_health, "task_results", lambda: None)
    monkeypatch.setattr(job_health, "latest_write", locked)
    lines = job_health.report(tmp_path / "x.db", NOW, repo=tmp_path)
    assert lines == [
        "WARN snapshot: could not read DB (database is locked) — retry later",
        "WARN NLP recluster: could not read DB (database is locked) — retry later",
    ]


def test_report_uses_task_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        job_health, "task_results", lambda: {"ThreadsAI_SnapshotJob_4h": task(0xC000013A)}
    )
    lines = job_health.report(tmp_path / "missing.db", NOW, repo=tmp_path)
    assert lines[0].startswith("WARN snapshot") and "0xC000013A" in lines[0]
    assert lines[1].startswith("WARN NLP recluster") and "LastTaskResult" not in lines[1]


def test_contract_run_logged_lines_are_read_by_last_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Hợp đồng giữa 2 phía: dòng do job thật ghi ra phải được job_health đọc được, và tên job
    # trong JobSpec phải trùng tên entry point dùng — đổi 1 bên là mất phát hiện thành công.
    import src.pipeline.ingest as ingest
    from src.pipeline import nlp_cluster_job, scheduled_job

    async def fake_ingest(*, use_cache: bool) -> dict[str, int]:
        return {}

    monkeypatch.setattr(ingest, "run_ingest", fake_ingest)
    monkeypatch.setattr(nlp_cluster_job, "build_steps", lambda repo, python: [])
    snap_log, nlp_log = tmp_path / "s.log", tmp_path / "n.log"
    assert scheduled_job.main([], status_log=snap_log) == 0
    assert nlp_cluster_job.main([], status_log=nlp_log) == 0
    assert job_health.last_success(snap_log, SNAPSHOT.job_name) is not None
    assert job_health.last_success(nlp_log, NLP.job_name) is not None
    snap_rel = scheduled_job.LOG_PATH.relative_to(scheduled_job.REPO_ROOT).as_posix()
    nlp_rel = nlp_cluster_job.LOG_PATH.relative_to(nlp_cluster_job.REPO_ROOT).as_posix()
    assert (snap_rel, nlp_rel) == (SNAPSHOT.log, NLP.log)
