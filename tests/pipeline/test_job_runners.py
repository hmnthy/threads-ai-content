"""Test launcher cron không console (ADR-0013).

Log tự ghi (UTF-8, có dòng bắt đầu/kết thúc), mã thoát, job NLP dừng khi 1 bước lỗi.
Mô phỏng `pythonw`: `sys.stdout`/`sys.stderr` là None cho tới khi mở log.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path, PureWindowsPath
from typing import Any, TextIO

import pytest

from src.pipeline import job_log, nlp_cluster_job, scheduled_job


@pytest.fixture
def pythonw_streams(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Như pythonw: không có stdout/stderr. Đóng file log mà job mở khi test xong.

    Ghi lại stream do `redirect_output` mở (không đóng `sys.stdout` lúc teardown: khi đó
    pytest đã gán lại stream capture của nó)."""
    opened: list[TextIO] = []
    real_redirect = job_log.redirect_output

    def recording_redirect(log_path: Path) -> TextIO:
        stream = real_redirect(log_path)
        opened.append(stream)
        return stream

    monkeypatch.setattr(job_log, "redirect_output", recording_redirect)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    yield
    for stream in opened:
        stream.close()


def test_run_logged_failure_writes_traceback_utf8(tmp_path: Path, pythonw_streams: None) -> None:
    log = tmp_path / "logs" / "job.log"
    log.parent.mkdir()
    log.write_text("dòng cũ\n", encoding="utf-8")
    job_log.redirect_output(log)

    def boom() -> None:
        raise ValueError("hỏng")

    assert job_log.run_logged("demo", boom) == 1
    text = log.read_text(encoding="utf-8")
    assert text.startswith("dòng cũ\n")  # append, không ghi đè
    assert "demo bắt đầu" in text
    assert "Traceback" in text and "ValueError: hỏng" in text
    assert "demo LỖI (exit 1)" in text  # tiếng Việt nguyên vẹn, không phải chuỗi escape


def test_run_logged_success_writes_start_and_end(capsys: pytest.CaptureFixture[str]) -> None:
    assert job_log.run_logged("demo", lambda: {"posts": 3}) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].endswith("demo bắt đầu")
    assert out[1].endswith("demo xong (exit 0): {'posts': 3}")


def test_log_path_from_argv() -> None:
    assert job_log.log_path_from_argv(["--log", "a.log"]) == Path("a.log")
    assert job_log.log_path_from_argv(["--log=b.log"]) == Path("b.log")
    assert job_log.log_path_from_argv(["--log"]) is None
    assert job_log.log_path_from_argv([]) is None


def test_bad_argument_under_pythonw_is_logged(tmp_path: Path, pythonw_streams: None) -> None:
    log = tmp_path / "job.log"
    code = job_log.run_job("demo", "d", lambda: 1, ["--log", str(log), "--bogus"])
    assert code == 2
    assert "unrecognized arguments: --bogus" in log.read_text(encoding="utf-8")


def test_no_log_under_pythonw_does_not_crash(pythonw_streams: None) -> None:
    # Chạy pythonw mà quên --log: không có chỗ ghi, nhưng vẫn phải trả mã thoát đúng
    assert job_log.run_job("demo", "d", lambda: 1, []) == 0
    assert job_log.run_job("demo", "d", lambda: 1 / 0, []) == 1


def test_scheduled_job_import_error_lands_in_log(
    tmp_path: Path, pythonw_streams: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Module dự án import TRONG body → lỗi import (VD đang `uv sync` dở) có traceback trong log
    monkeypatch.setitem(sys.modules, "src.pipeline.ingest", None)
    log = tmp_path / "scheduled_job.log"
    assert scheduled_job.main(["--log", str(log)]) == 1
    text = log.read_text(encoding="utf-8")
    assert "scheduled_job bắt đầu" in text
    assert "ImportError" in text or "ModuleNotFoundError" in text


def test_scheduled_job_success(
    tmp_path: Path, pythonw_streams: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_ingest(*, use_cache: bool) -> dict[str, int]:
        assert use_cache is False  # chu kỳ 4h < TTL cache 6h
        return {"posts": 1}

    import src.pipeline.ingest as ingest

    monkeypatch.setattr(ingest, "run_ingest", fake_ingest)
    log = tmp_path / "scheduled_job.log"
    assert scheduled_job.main(["--log", str(log)]) == 0
    assert "scheduled_job xong (exit 0): {'posts': 1}" in log.read_text(encoding="utf-8")


def test_wsl_path() -> None:
    repo = PureWindowsPath(r"C:\Users\hmnth\Desktop\repo")
    assert nlp_cluster_job.wsl_path(repo) == "/mnt/c/Users/hmnth/Desktop/repo"
    with pytest.raises(ValueError):
        nlp_cluster_job.wsl_path(PureWindowsPath("relative\\path"))


def test_console_python_swaps_pythonw_only() -> None:
    swapped = nlp_cluster_job.console_python(r"C:\v\Scripts\pythonw.exe")
    assert swapped == r"C:\v\Scripts\python.exe"
    assert nlp_cluster_job.console_python(r"C:\v\Scripts\python.exe") == r"C:\v\Scripts\python.exe"
    assert nlp_cluster_job.console_python("/usr/bin/python3") == "/usr/bin/python3"


def test_build_steps_order_and_wsl_command() -> None:
    steps = nlp_cluster_job.build_steps(PureWindowsPath(r"C:\repo"), "py.exe")
    assert [s.name for s in steps] == ["export", "cluster_wsl", "import"]
    assert steps[0].argv == ["py.exe", "-m", "src.pipeline.clustering_export"]
    wsl = steps[1].argv
    assert wsl[:5] == ["wsl", "-d", "Ubuntu", "--", "bash"]
    assert wsl[-1].startswith("cd /mnt/c/repo && source ")
    assert wsl[-1].endswith("python3 -m src.pipeline.cluster_wsl")


def test_run_steps_stops_at_first_failure() -> None:
    calls: list[str] = []

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        calls.append(argv[0])
        assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
        return subprocess.CompletedProcess(argv, 1 if argv[0] == "b" else 0)

    steps = [nlp_cluster_job.Step(n, [n]) for n in ("a", "b", "c")]
    with pytest.raises(RuntimeError, match="bước b lỗi"):
        nlp_cluster_job.run_steps(steps, runner=runner)
    assert calls == ["a", "b"]  # import (bước sau) không chạy trên export hỏng


def test_run_steps_real_children_share_the_log_in_order(
    tmp_path: Path, pythonw_streams: None
) -> None:
    # Tiến trình con thật ghi vào CÙNG file log qua handle kế thừa, đúng thứ tự, đúng UTF-8
    log = tmp_path / "nlp.log"
    job_log.redirect_output(log)
    child = [
        sys.executable,
        "-c",
        "import sys; print('con: Tiếng Việt'); print('lỗi con', file=sys.stderr)",
    ]
    steps = [nlp_cluster_job.Step("s1", child), nlp_cluster_job.Step("s2", child)]
    assert nlp_cluster_job.run_steps(steps) == ["s1", "s2"]
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "-- bước s1",
        "con: Tiếng Việt",
        "lỗi con",
        "-- bước s2",
        "con: Tiếng Việt",
        "lỗi con",
    ]


def test_abbreviated_log_flag_is_rejected(tmp_path: Path, pythonw_streams: None) -> None:
    # `--lo x` không được log_path_from_argv nhận → argparse phải từ chối, không chạy câm
    assert job_log.run_job("demo", "d", lambda: 1, ["--lo", str(tmp_path / "x.log")]) == 2


def test_manual_run_without_log_still_records_status(tmp_path: Path) -> None:
    # Chạy tay ra màn hình: dòng bắt đầu/kết thúc vẫn vào log chuẩn → job_health thấy thành công
    status = tmp_path / "logs" / "job.log"
    assert job_log.run_job("demo", "d", lambda: {"ok": 1}, [], status_log=status) == 0
    lines = status.read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("demo bắt đầu")
    assert lines[1].endswith("demo xong (exit 0): {'ok': 1}")


def test_status_log_not_duplicated_when_log_given(tmp_path: Path, pythonw_streams: None) -> None:
    log = tmp_path / "job.log"
    job_log.run_job("demo", "d", lambda: 1, ["--log", str(log)], status_log=log)
    assert log.read_text(encoding="utf-8").count("demo bắt đầu") == 1


def test_status_log_write_failure_does_not_change_result(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")  # status_log nằm "trong" 1 file → OSError
    assert job_log.run_job("demo", "d", lambda: 1, [], status_log=blocker / "job.log") == 0
