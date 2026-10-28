"""Bước publish bản sao DB lên Blob sau mỗi job (ADR-0025 bước 3). Không gọi mạng: hàm tải lên
được thay bằng bản giả; `tests/conftest.py` còn chặn mọi lần tải thật ở mọi test."""

from __future__ import annotations

import inspect
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

import src.db.schema as schema_module
import src.pipeline.publish as publish_module
from src.db.published import ROLLBACK_JOURNAL_FLAGS
from src.db.schema import connect_readonly
from src.pipeline.publish import PublishState, make_copy, publish, publish_after_job
from src.pipeline.publish import vercel_upload as _real_vercel_upload
from tests.test_main import _seed_full_db

# định dạng token đọc-ghi của Vercel Blob: vercel_blob_rw_<store id>_<secret> (giả)
FAKE_TOKEN = "vercel_blob_rw_AbC123_s3cr3t"


class FakeUpload:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, bytes, str | None]] = []

    def __call__(self, pathname: str, body: bytes, token: str | None = None) -> None:
        self.calls.append((pathname, body, token))
        if self.fail:
            raise ConnectionError("Blob unreachable")


@pytest.fixture
def source_db(tmp_path: Path) -> Path:
    path = tmp_path / "laptop" / "threads.db"
    path.parent.mkdir()
    _seed_full_db(path)  # 1 snapshot, fetched_at 2026-08-30 12:00 UTC
    return path


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".env"
    path.write_text(
        f"DB_BLOB_PATH=db/threads.db\nBLOB_READ_WRITE_TOKEN={FAKE_TOKEN}\n", encoding="utf-8"
    )
    monkeypatch.setattr(publish_module, "ENV_FILE", path)
    return path


def _post_ids(path: Path) -> list[str]:
    conn = connect_readonly(path)
    try:
        return [r[0] for r in conn.execute("SELECT id FROM posts ORDER BY id")]
    finally:
        conn.close()


def test_copy_of_a_wal_database_is_rollback_journal(source_db: Path, tmp_path: Path) -> None:
    conn = sqlite3.connect(source_db)
    assert conn.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
    conn.close()
    assert source_db.read_bytes()[18:20] == b"\x02\x02"  # dữ liệu test thật sự ở WAL (Phase C)

    copy = tmp_path / "copy.db"
    make_copy(source_db, copy)

    assert copy.read_bytes()[18:20] == ROLLBACK_JOURNAL_FLAGS
    assert _post_ids(copy) == _post_ids(source_db) == ["post-1"]


def test_copy_gives_up_on_a_locked_source_instead_of_hanging(
    source_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # writer giữ khoá chặn mọi reader (như 1 commit lỗi kẹt ở PENDING trong `finally` của job):
    # `Connection.backup` một mình sẽ thử lại mãi → chạy trong luồng riêng có hạn để test không treo
    monkeypatch.setattr(schema_module, "LOCK_WAIT_S", 0.2)
    writer = sqlite3.connect(source_db, timeout=0)
    writer.execute("BEGIN EXCLUSIVE")
    outcome: list[BaseException | None] = []

    def run() -> None:
        try:
            make_copy(source_db, tmp_path / "copy.db")
            outcome.append(None)
        except BaseException as exc:
            outcome.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    try:
        worker.start()
        worker.join(timeout=10)
        assert not worker.is_alive(), "make_copy hung on a locked source"
    finally:
        writer.rollback()
        writer.close()
    (exc,) = outcome
    assert isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc)


def test_publish_uploads_copy_and_writes_state(source_db: Path, tmp_path: Path) -> None:
    upload = FakeUpload()
    state_path = tmp_path / "logs" / "publish_state.json"

    state = publish(source_db, "db/threads.db", upload=upload, state_path=state_path)

    ((pathname, body, _),) = upload.calls
    assert pathname == "db/threads.db"
    uploaded = tmp_path / "uploaded.db"
    uploaded.write_bytes(body)
    assert _post_ids(uploaded) == ["post-1"]  # đúng là 1 DB đọc được, không phải file rỗng
    assert state.size_bytes == len(body)
    assert state.latest_snapshot_at is not None
    assert state.latest_snapshot_at.startswith("2026-08-30T12:00")
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["published_at"] == state.published_at
    assert saved["latest_snapshot_at"] == state.latest_snapshot_at
    assert list(state_path.parent.glob("*.tmp")) == []


def test_failed_upload_keeps_previous_state(source_db: Path, tmp_path: Path) -> None:
    state_path = tmp_path / "publish_state.json"
    state_path.write_text('{"published_at": "2026-10-20T08:00:00+00:00"}', encoding="utf-8")

    with pytest.raises(ConnectionError):
        publish(source_db, "threads.db", upload=FakeUpload(fail=True), state_path=state_path)

    # mốc cũ giữ nguyên → job_health thấy bản publish cũ đi
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "published_at": "2026-10-20T08:00:00+00:00"
    }


def test_after_job_reads_this_checkout_env_and_publishes(
    source_db: Path,
    env_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    upload = FakeUpload()
    monkeypatch.setattr(publish_module, "vercel_upload", upload)

    state = publish_after_job(source_db)

    assert isinstance(state, PublishState) and state.blob_path == "db/threads.db"
    assert [(p, t) for p, _, t in upload.calls] == [("db/threads.db", FAKE_TOKEN)]
    saved = json.loads(publish_module.STATE_PATH.read_text(encoding="utf-8"))
    assert saved["blob_path"] == "db/threads.db"
    assert "publish: OK" in capsys.readouterr().out


def test_after_job_skips_when_not_configured(
    source_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    upload = FakeUpload()
    monkeypatch.setattr(publish_module, "vercel_upload", upload)

    assert publish_after_job(source_db) is None

    assert upload.calls == []
    assert "publish: skipped" in capsys.readouterr().out


def test_after_job_ignores_settings_only_in_os_environ(
    source_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # worktree: `load_dotenv()` của src/api/auth.py đi ngược lên và nạp .env của thư mục chính
    # vào os.environ — publish không được dùng nó để đè bản công khai bằng DB của worktree
    monkeypatch.setenv("DB_BLOB_PATH", "db/threads.db")
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", FAKE_TOKEN)
    upload = FakeUpload()
    monkeypatch.setattr(publish_module, "vercel_upload", upload)

    assert publish_after_job(source_db) is None
    assert upload.calls == []
    assert "publish: skipped" in capsys.readouterr().out


def test_after_job_skips_in_a_linked_worktree(
    source_db: Path,
    env_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # worktree có .env riêng (git-flow bước 5 copy sang) — vẫn không publish
    (publish_module.REPO_ROOT / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    upload = FakeUpload()
    monkeypatch.setattr(publish_module, "vercel_upload", upload)

    assert publish_after_job(source_db) is None
    assert upload.calls == []
    assert "linked worktree" in capsys.readouterr().out


def test_after_job_missing_token_fails_without_upload(
    source_db: Path,
    env_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file.write_text("DB_BLOB_PATH=db/threads.db\n", encoding="utf-8")
    upload = FakeUpload()
    monkeypatch.setattr(publish_module, "vercel_upload", upload)

    assert publish_after_job(source_db) is None
    assert upload.calls == []
    captured = capsys.readouterr()
    assert "publish: FAILED" in captured.out
    assert "BLOB_READ_WRITE_TOKEN" in captured.err


def test_after_job_never_raises_and_does_not_repeat_the_job_traceback(
    source_db: Path,
    env_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(publish_module, "vercel_upload", FakeUpload(fail=True))

    try:
        raise RuntimeError("ingest exploded")
    except RuntimeError:
        # như trong `finally` của job: 1 exception khác đang lan ra
        assert publish_after_job(source_db) is None

    captured = capsys.readouterr()
    assert "publish: FAILED" in captured.out
    assert "ConnectionError" in captured.err  # traceback của publish vào log của job
    assert "ingest exploded" not in captured.err  # không in lại lỗi của job (chain=False)
    assert not publish_module.STATE_PATH.exists()


def test_conftest_refuses_real_uploads(source_db: Path, env_file: Path) -> None:
    # chốt chặn chung: test nào lỡ bật publish cũng không tải gì lên Vercel — và lỗi xuyên qua
    # `except Exception` của publish_after_job (pytest.fail là BaseException) thay vì bị nuốt
    with pytest.raises(pytest.fail.Exception, match="a test tried to upload"):
        publish_after_job(source_db)


def test_vercel_upload_pins_read_write_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hợp đồng với SDK `vercel-blob` ghim `==` (không gọi mạng): đúng hàm + tham số đang dùng, và
    credential là token đọc-ghi kể cả khi môi trường có OIDC + BLOB_STORE_ID (mặc định SDK sẽ ưu
    tiên OIDC)."""
    import vercel.blob.sync as blob_sync
    from vercel._internal.core.session import get_active_sync_session

    params = inspect.signature(blob_sync.put_blob).parameters
    assert {"access", "content_type", "add_random_suffix", "allow_overwrite"} <= set(params)

    monkeypatch.setenv("BLOB_STORE_ID", "store_other")
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "oidc-from-vercel-env-pull")
    seen: dict[str, Any] = {}

    def fake_put_blob(pathname: str, body: bytes, **kwargs: Any) -> None:
        session = get_active_sync_session()
        options = session.get_service_option(blob_sync.SyncBlobServiceOptions)
        assert options is not None
        seen.update(pathname=pathname, kwargs=kwargs, creds=options.credentials_factory())

    monkeypatch.setattr(blob_sync, "put_blob", fake_put_blob)

    # `_real_vercel_upload` lấy lúc import file test, trước khi conftest thay bằng bản từ chối
    _real_vercel_upload("db/threads.db", b"x", FAKE_TOKEN)

    creds = seen["creds"]
    assert (creds.token, creds.kind) == (FAKE_TOKEN, blob_sync.CredentialKind.READ_WRITE)
    assert creds.store_id.lower() == "abc123"  # tách từ token, không phải store_other
    assert seen["kwargs"]["access"] == "private"
    assert seen["kwargs"]["allow_overwrite"] is True
    assert seen["kwargs"]["add_random_suffix"] is False
