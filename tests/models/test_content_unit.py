from datetime import UTC, datetime

from src.api.models import MediaType, ThreadsPost
from src.models.content_unit import ContentUnit


def _post(post_id: str) -> ThreadsPost:
    return ThreadsPost(
        id=post_id,
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )


def test_content_unit_id_is_root_post_id() -> None:
    unit = ContentUnit(root=_post("root-1"), full_text="hello")
    assert unit.id == "root-1"


def test_content_unit_defaults_are_empty() -> None:
    unit = ContentUnit(root=_post("root-1"), full_text="hello")
    assert unit.continuations == []
    assert unit.media == []
    assert unit.text_attachment is None
    assert unit.is_multi_post is False


def test_content_unit_is_multi_post_when_continuations_present() -> None:
    unit = ContentUnit(root=_post("root-1"), continuations=[_post("c-1")], full_text="hello world")
    assert unit.is_multi_post is True
