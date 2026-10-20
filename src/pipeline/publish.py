"""Publish bản sao DB lên Vercel Blob riêng tư sau mỗi job (ADR-0025, Hệ quả bước 3).

API trên Vercel đọc bản sao này (`src/db/published.py`). Gọi ở cuối 2 cron job
(`scheduled_job`, `nlp_cluster_job`) qua `publish_after_job()` — hàm KHÔNG BAO GIỜ raise:
publish lỗi không được làm hỏng job chính; lần chạy sau thử lại.

1. Bản sao nhất quán bằng backup API của SQLite (không copy file đang có thể bị ghi), đặt
   `journal_mode = DELETE` — API từ chối bản sao mang cờ WAL (`ROLLBACK_JOURNAL_FLAGS`).
2. Tải lên Blob riêng tư, ghi đè cùng pathname (`DB_BLOB_PATH`), bằng `BLOB_READ_WRITE_TOKEN`
   (SDK `vercel-blob`, store id tách từ chính token). Chỉ đọc DB nguồn, không ghi gì vào DB →
   không tranh khoá ghi với job.
3. Thành công → ghi `data/logs/publish_state.json` (file trạng thái: lần publish thành công gần
   nhất + mốc snapshot trong bản sao) — `scripts/job_health.py` cảnh báo khi file này cũ. Chỉ ghi
   khi thành công: job bị giết giữa chừng thì mốc cũ đi, không có dòng "OK" giả.

Chỉ thư mục chính publish: cấu hình đọc từ `.env` CỦA CHÍNH checkout (`dotenv_values`), không từ
`os.environ` — `load_dotenv()` không đường dẫn ở `src/api/auth.py` đi ngược lên thư mục cha nên
một worktree (`.claude/worktrees/…`, ADR-0019) nhận cả `.env` của thư mục chính; và worktree
(`.git` là file) luôn bỏ qua: DB của worktree có thể cũ, không được đè bản công khai.

Hạn chế chấp nhận: 2 job kết thúc gần nhau (chạy chồng sau khi máy thức dậy, ADR-0017) có thể tải
lên không theo thứ tự → bản cũ hơn đè bản mới tới lần publish kế tiếp (≤ 4h). DB nguồn bị khoá
lâu → publish lỗi sau `LOCK_WAIT_S` (khoá đọc giành trước `backup`, xem `make_copy`), lần sau thử
lại.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.db.published import BLOB_PATH_ENV, ROLLBACK_JOURNAL_FLAGS, SQLITE_HEADER
from src.db.schema import DEFAULT_DB_PATH, connect, connect_readonly, latest_snapshot_time

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = REPO_ROOT / "data" / "logs" / "publish_state.json"
ENV_FILE = REPO_ROOT / ".env"
TOKEN_ENV = "BLOB_READ_WRITE_TOKEN"
CONTENT_TYPE = "application/vnd.sqlite3"

Uploader = Callable[[str, bytes], None]


@dataclass(frozen=True)
class PublishState:
    published_at: str  # UTC ISO, lúc tải lên xong
    latest_snapshot_at: str | None  # `fetched_at` mới nhất TRONG bản sao (mốc số liệu công khai)
    blob_path: str
    size_bytes: int


def make_copy(src: Path, dest: Path) -> None:
    """Bản sao nhất quán của `src` vào `dest` (file mới), ở rollback journal."""
    source = connect_readonly(src)
    try:
        # Giành khoá đọc CÓ GIỚI HẠN trước: `Connection.backup` của CPython thử lại không giới hạn
        # khi DB bận (timeout của connection không chặn được vòng lặp đó). Bị chặn (VD writer kẹt
        # ở PENDING sau 1 commit lỗi) → `database is locked` sau `LOCK_WAIT_S` thay vì treo job.
        source.execute("BEGIN")
        source.execute("SELECT count(*) FROM sqlite_master").fetchone()
        target = connect(dest)
        try:
            # 1 bước (pages = -1 mặc định) trong read transaction trên: ảnh nhất quán ~8 MB, không
            # thấy dữ liệu ghi dở của job khác
            source.backup(target)
            mode = target.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
        finally:
            target.close()
    finally:
        source.close()
    if str(mode).lower() != "delete":
        raise RuntimeError(f"copy is in journal_mode={mode}, expected delete")
    with dest.open("rb") as f:
        header = f.read(20)
    if header[:16] != SQLITE_HEADER or header[18:20] != ROLLBACK_JOURNAL_FLAGS:
        raise RuntimeError("copy header is not an SQLite rollback-journal database")


def _snapshot_mark(copy: Path) -> str | None:
    conn = connect_readonly(copy)
    try:
        return latest_snapshot_time(conn)
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return None
        raise
    finally:
        conn.close()


def write_state(state: PublishState, path: Path) -> None:
    """Ghi nguyên tử (file tạm tên riêng + os.replace): `job_health` không bao giờ đọc file ghi
    dở, 2 job kết thúc gần nhau không ghi chồng cùng 1 file tạm."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.stem, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, indent=2)
        os.replace(tmp_name, path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def publish(
    db_path: Path,
    blob_path: str,
    *,
    upload: Uploader,
    state_path: Path,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PublishState:
    """Sao chép → tải lên → ghi file trạng thái. Lỗi ở bất kỳ bước nào → raise, file trạng thái
    giữ nguyên (mốc cũ)."""
    # ignore_cleanup_errors: antivirus/indexer có thể giữ file .db mới tạo trong %TEMP% — lỗi
    # dọn thư mục tạm không được làm hỏng 1 lần publish
    with tempfile.TemporaryDirectory(
        prefix="unthreaded-publish-", ignore_cleanup_errors=True
    ) as tmp:
        copy = Path(tmp) / "threads.db"
        make_copy(db_path, copy)
        mark = _snapshot_mark(copy)
        body = copy.read_bytes()
    upload(blob_path, body)
    state = PublishState(
        published_at=now().isoformat(timespec="seconds"),
        latest_snapshot_at=mark,
        blob_path=blob_path,
        size_bytes=len(body),
    )
    write_state(state, state_path)
    return state


def vercel_upload(pathname: str, body: bytes, token: str) -> None:
    """Tải lên Blob riêng tư bằng SDK chính thức (`vercel-blob`, nhóm thư viện `pipeline` — không
    nằm trong gói API). Credential ghim tường minh vào token đọc-ghi: mặc định SDK ưu tiên OIDC khi
    môi trường có `BLOB_STORE_ID` + `VERCEL_OIDC_TOKEN` (VD sau `vercel env pull`) — token đó hết
    hạn ~12h và có thể trỏ store khác. `store_from_read_write_token` là helper nội bộ của SDK →
    phiên bản ghim `==` trong pyproject + test hợp đồng (tests/pipeline/test_publish.py)."""
    from vercel.api import session
    from vercel.blob._internal.credentials import store_from_read_write_token
    from vercel.blob.sync import (
        BlobCredentials,
        CredentialKind,
        SyncBlobServiceOptions,
        put_blob,
    )

    credentials = BlobCredentials(
        token, store_from_read_write_token(token), CredentialKind.READ_WRITE
    )
    options = SyncBlobServiceOptions(credentials_factory=lambda: credentials)
    with session(service_options=[options]):
        put_blob(
            pathname,
            body,
            access="private",
            content_type=CONTENT_TYPE,
            add_random_suffix=False,
            allow_overwrite=True,
        )


def publish_after_job(db_path: Path = DEFAULT_DB_PATH) -> PublishState | None:
    """Bước cuối của mỗi cron job. Không bao giờ raise — in kết quả vào log của job.
    `REPO_ROOT`, `ENV_FILE`, `vercel_upload`, `STATE_PATH` tra lúc gọi (không bind làm giá trị mặc
    định) để `tests/conftest.py` chặn được việc tải dữ liệu thật lên Blob ở MỌI test chạm vào
    job."""
    try:
        if (REPO_ROOT / ".git").is_file():
            print(
                "publish: skipped (linked worktree — only the main checkout publishes)", flush=True
            )
            return None
        from dotenv import dotenv_values

        config = dotenv_values(ENV_FILE)  # chỉ .env của checkout này, không đọc os.environ
        blob_path = (config.get(BLOB_PATH_ENV) or "").strip()
        if not blob_path:
            print(f"publish: skipped ({BLOB_PATH_ENV} not set in {ENV_FILE.name})", flush=True)
            return None
        token = (config.get(TOKEN_ENV) or "").strip()
        if not token:
            raise RuntimeError(f"{TOKEN_ENV} is not set in {ENV_FILE.name}")
        upload = vercel_upload

        def _upload(pathname: str, body: bytes) -> None:
            upload(pathname, body, token)

        state = publish(db_path, blob_path, upload=_upload, state_path=STATE_PATH)
    except Exception as exc:
        print("publish: FAILED — the public site keeps the previous copy", flush=True)
        # chain=False: gọi trong `finally` khi job đã lỗi → không lồng traceback của job
        # (`run_logged` in nó ngay sau, kèm dòng kết thúc) vào khối lỗi publish
        traceback.print_exception(exc, chain=False)
        return None
    print(
        f"publish: OK ({state.size_bytes} bytes, data to {state.latest_snapshot_at})",
        flush=True,
    )
    return state
