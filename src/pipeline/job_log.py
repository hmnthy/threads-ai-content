"""Ghi log cho job chạy không giám sát (Task Scheduler) — ADR-0013.

Task Scheduler gọi thẳng `pythonw.exe` (không console). Lý do: khi task mở cửa sổ
console (Windows Terminal tiếp quản), cửa sổ đó đóng là cả job bị giết với
`0xC000013A` (STATUS_CONTROL_C_EXIT) — không kịp ghi dòng log nào. `pythonw` không
có stdout/stderr (`sys.stdout is None`), nên job tự mở file log và trỏ cả 2 luồng
vào đó: mọi `print`, cảnh báo thư viện và traceback chưa bắt đều vào log, mã hoá
UTF-8 (redirect `>>` của cmd dùng cp1252 → chữ "Ỗ" của "LỖI" bị in thành chuỗi escape
"L\\u1ed6I").

Thứ tự bắt buộc trong entry point: mở log → parse tham số → import module dự án (trong
`body`). Lỗi ở bất kỳ bước nào sau khi mở log đều có traceback trong log.

Mỗi lần chạy ghi 1 dòng "bắt đầu" và 1 dòng kết thúc có mã thoát → đọc log biết
được job chưa chạy, bị giết giữa chừng (có "bắt đầu", không có kết thúc) hay lỗi.
Chạy tay không `--log` (output ra màn hình) thì 2 dòng này VẪN được ghi thêm vào log
chuẩn của job (`status_log`): `scripts/job_health.py` dựa vào dòng kết thúc để biết đã
có lần chạy thành công — bằng chứng sức khoẻ không được phụ thuộc vào 1 cờ CLI.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO


def redirect_output(log_path: Path) -> TextIO:
    """Trỏ stdout + stderr vào `log_path` (append, UTF-8, ghi theo dòng)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream = log_path.open("a", encoding="utf-8", buffering=1)
    sys.stdout = stream
    sys.stderr = stream
    return stream


def log_path_from_argv(argv: Sequence[str]) -> Path | None:
    """Đọc `--log PATH` / `--log=PATH` thô, TRƯỚC argparse (lỗi argparse cần có chỗ ghi)."""
    for i, arg in enumerate(argv):
        if arg == "--log" and i + 1 < len(argv):
            return Path(argv[i + 1])
        if arg.startswith("--log="):
            return Path(arg.split("=", 1)[1])
    return None


def run_logged(name: str, body: Callable[[], object], status_log: Path | None = None) -> int:
    """Chạy `body`, in dòng bắt đầu/kết thúc kèm mã thoát. Trả mã thoát (0 = OK).

    `status_log`: ghi thêm 2 dòng đó vào file này (khi output KHÔNG đi vào log chuẩn).
    Exception được in đủ traceback rồi đổi thành mã 1 — không nuốt lỗi im lặng,
    Task Scheduler vẫn thấy `LastTaskResult` = 1.
    """

    def emit(line: str) -> None:
        print(line, flush=True)
        if status_log is None:
            return
        try:  # bằng chứng phụ — ghi lỗi (file bị khoá…) không được đổi kết quả của job
            status_log.parent.mkdir(parents=True, exist_ok=True)
            with status_log.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as exc:
            print(f"(không ghi được {status_log}: {exc!r})", flush=True)

    started = datetime.now(UTC).isoformat()
    emit(f"[{started}] {name} bắt đầu")
    try:
        result = body()
    except Exception as exc:  # noqa: BLE001 — job không giám sát: ghi lỗi + mã thoát, không crash câm
        traceback.print_exc()
        emit(f"[{started} -> {datetime.now(UTC).isoformat()}] {name} LỖI (exit 1): {exc!r}")
        return 1
    emit(f"[{started} -> {datetime.now(UTC).isoformat()}] {name} xong (exit 0): {result}")
    return 0


def run_job(
    name: str,
    description: str,
    body: Callable[[], object],
    argv: Sequence[str] | None = None,
    status_log: Path | None = None,
) -> int:
    """Entry point chung: mở log (nếu có `--log`) → parse tham số → `run_logged(body)`.

    Tham số sai → mã 2 (quy ước argparse), thông báo lỗi nằm trong log.
    `status_log` = log chuẩn của job; chỉ dùng khi không có `--log` (chạy tay ra màn hình).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    log = log_path_from_argv(args)
    if log is not None:
        redirect_output(log)
    # allow_abbrev=False: `--lo x` sẽ không được log_path_from_argv nhận ra
    parser = argparse.ArgumentParser(description=description, allow_abbrev=False)
    parser.add_argument(
        "--log", type=Path, help="file log (append) — bắt buộc khi chạy bằng pythonw"
    )
    try:
        parser.parse_args(args)
    except SystemExit as exc:  # --help (0) hoặc tham số sai (2); argparse đã in ra log
        return exc.code if isinstance(exc.code, int) else 2
    return run_logged(name, body, status_log if log is None else None)
