import json
import time
from pathlib import Path

from src.api.cache import Cache


def test_set_then_get_returns_same_data(tmp_path: Path) -> None:
    cache = Cache(cache_dir=tmp_path, ttl_seconds=3600)
    cache.set("posts_123", {"foo": "bar"})
    assert cache.get("posts_123") == {"foo": "bar"}


def test_get_missing_key_returns_none(tmp_path: Path) -> None:
    cache = Cache(cache_dir=tmp_path, ttl_seconds=3600)
    assert cache.get("does_not_exist") is None


def test_get_expired_entry_returns_none(tmp_path: Path) -> None:
    cache = Cache(cache_dir=tmp_path, ttl_seconds=1)
    cache.set("posts_123", {"foo": "bar"})
    path = cache._path_for("posts_123")
    stale = json.loads(path.read_text(encoding="utf-8"))
    stale["cached_at"] = time.time() - 10  # force it well past the 1s TTL
    path.write_text(json.dumps(stale), encoding="utf-8")
    assert cache.get("posts_123") is None


def test_clear_removes_entry(tmp_path: Path) -> None:
    cache = Cache(cache_dir=tmp_path, ttl_seconds=3600)
    cache.set("posts_123", {"foo": "bar"})
    cache.clear("posts_123")
    assert cache.get("posts_123") is None


def test_key_with_slashes_and_colons_is_sanitized_to_a_valid_path(tmp_path: Path) -> None:
    cache = Cache(cache_dir=tmp_path, ttl_seconds=3600)
    cache.set("user/123:posts", {"foo": "bar"})
    assert cache.get("user/123:posts") == {"foo": "bar"}
