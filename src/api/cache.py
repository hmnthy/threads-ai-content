from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DEFAULT_CACHE_DIR = Path("data/cache")
DEFAULT_TTL_SECONDS = (
    6 * 60 * 60
)  # 6 hours, per docs/claude/architecture.md decision to avoid Threads rate limits


class Cache:
    """JSON file cache with TTL, used to avoid re-hitting the Threads API within the same window."""

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Any | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - payload["cached_at"] > self.ttl_seconds:
            return None
        return payload["data"]

    def set(self, key: str, data: Any) -> None:
        path = self._path_for(key)
        payload = {"cached_at": time.time(), "data": data}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def clear(self, key: str) -> None:
        self._path_for(key).unlink(missing_ok=True)
