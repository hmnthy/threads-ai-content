"""19 content unit đóng băng của demo RAG (ADR-0037 D2, ADR-0040): danh sách mã + độ dài + hash.

Đóng băng bằng danh sách chứ không bằng "20 bài mới nhất": bài mới đăng sau mốc không được đẩy bài
cũ ra khỏi tập, vì 10 câu hỏi và 2 vị trí đáp án gắn với đúng các bài này. Thy chọn 2026-11-06.
Mốc đóng băng có 20 bài; `18117744790996401` bị tác giả xoá trên Threads sau mốc nên bỏ, không lấy
bài khác thay (ADR-0040, Thy chọn 2026-11-08).

CI không có DB thật (`data/` gitignored): chốt chặn "bài còn nguyên" nằm ở code đọc dữ liệu, chạy ở
bước dựng, test dùng DB tự chế. Độ dài lưu sẵn để CI vẫn kiểm được 2 vị trí đáp án nằm trong bài
(ADR-0038 Hệ quả; Thy chọn 2026-11-07).
"""

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FrozenUnit:
    """Một bài đóng băng. Độ dài đếm theo điểm mã của Python; hash không dựng lại được chữ bài."""

    id: str
    length: int
    sha256: str


# Bài mới trước. Thứ tự này chính là thứ tự mã chunk, dùng phân hạng khi điểm bằng nhau
# (ADR-0038 D4).
FROZEN_UNITS: tuple[FrozenUnit, ...] = (
    FrozenUnit(
        "17994430959116980", 989, "49c724046e4e0219c4b084d7d4cb1851bd8aee71613df96a77a066c23a63eedd"
    ),
    FrozenUnit(
        "17914517928496891", 989, "f47424833f475eb4686e15815f6043d660fc5c38fba53b4250636e2acdb27589"
    ),
    FrozenUnit(
        "18115831448036192",
        2290,
        "1a656e3166ad90ec01f82e79b7b234c7c8a912cbb23ede70d5a9fbc23950b4b6",
    ),
    FrozenUnit(
        "18156311638533948",
        1262,
        "2c6da9e93960ced013eece4955f5e4b384f5032d62a15ee4af52047a19ae69fe",
    ),
    FrozenUnit(
        "18128851717831169",
        1497,
        "076221f6d4a714687a18d67098bc82a4330dedf3c1707cf9e72b0a21624081ef",
    ),
    FrozenUnit(
        "17923191900443021",
        2464,
        "b2cfe1f25519f8a2fb469a7be5836765cafff965658ff30e246ae3ac89b299a5",
    ),
    FrozenUnit(
        "18042552590841773",
        2625,
        "5057ff29ba302601bbe82baad776e527acd60a42eb8cdb14361f1cccaf4fc632",
    ),
    FrozenUnit(
        "17899007316608496",
        1173,
        "45b4d2d54bef6c8a30482e4004cda0353e145147ecaa1a3ce5041e926d0194ed",
    ),
    FrozenUnit(
        "18071804063761974", 481, "c38bdaf1e5dc4c19719503444ba55833abe64811d39a4dbf6620333165924f2b"
    ),
    FrozenUnit(
        "18645332647003724",
        1003,
        "a66aa7372e05dee2ee29536f82a7ea855da9aa431917ea8f7720e9e63748641c",
    ),
    FrozenUnit(
        "18153699859548704",
        1277,
        "f4cc1f0ea7b012950e53b7267ca17c4f5711d22d5adf94a3099388ead5b7d083",
    ),
    FrozenUnit(
        "18153254788534091",
        1304,
        "cb8a7c49fd10eea7bd6bb45066ad99df3e7cf1c1f9d932e8310ebd7f936eaf88",
    ),
    FrozenUnit(
        "17998567739826631", 203, "67e7bc8b4c14875ecd2a54130e4e156ba180f3674bc27d7b94a5a24862f15df6"
    ),
    FrozenUnit(
        "18102395354566129",
        1730,
        "4c8ff9bfcac0e90cc64e740598dcd552ebbd98a908f7a3579c09671c7a595f81",
    ),
    FrozenUnit(
        "17978356199920555",
        1413,
        "65fcfb1c6be7f2010f5e54aa2ba595c9a43226b0f023fbd39f9d42c7e6432ee8",
    ),
    FrozenUnit(
        "18138892390592446", 279, "63e254dc4aa9f480c89d8186eef6df141842e40fe982f0452cf3daa987e6ea83"
    ),
    # (chỗ của `18117744790996401`, bị xoá trên Threads — ADR-0040)
    FrozenUnit(
        "18128894426508078",
        1594,
        "aadf41eccd13d57b0de719032b6f8ec2cfe17ef9f6d9c0f6285da969f7b3942e",
    ),
    FrozenUnit(
        "18167259532477886",
        1113,
        "cd44b18a667a5bf1c04540dcae92c35c8cd93b1d3ab7494f8303c9915401f826",
    ),
    FrozenUnit(
        "18133654129644298",
        1351,
        "0f12e06ffcb6d0618eccb963a418bae6ebb4bd690990371f6d4d2c4857787c3b",
    ),
)


class CorpusChangedError(ValueError):
    """Dữ liệu không còn khớp danh sách đóng băng. Thông báo chỉ ghi mã bài, không ghi chữ bài."""


@dataclass(frozen=True)
class PostSpan:
    """Vị trí một post trong `full_text`, nửa mở, đếm theo điểm mã Unicode của Python."""

    post_id: str
    start: int
    end: int


@dataclass(frozen=True)
class Unit:
    id: str
    full_text: str
    posts: tuple[PostSpan, ...]


def content_hash(full_text: str) -> str:
    return hashlib.sha256(full_text.encode("utf-8")).hexdigest()


def _post_spans(
    conn: sqlite3.Connection, unit_id: str, post_ids: list[str], full_text: str
) -> tuple[PostSpan, ...]:
    """`full_text` (ADR-0004) là chữ các post ghép bằng dấu cách; post rỗng không góp chữ."""
    spans: list[PostSpan] = []
    texts: list[str] = []
    cursor = 0
    for post_id in post_ids:
        row = conn.execute("SELECT text FROM posts WHERE id = ?", (post_id,)).fetchone()
        text = row[0] if row is not None else None
        if not text:
            continue
        spans.append(PostSpan(post_id=post_id, start=cursor, end=cursor + len(text)))
        texts.append(text)
        cursor += len(text) + 1
    if " ".join(texts) != full_text:
        raise CorpusChangedError(f"{unit_id}: các post không ghép lại đúng full_text")
    return tuple(spans)


def load_units(
    conn: sqlite3.Connection, frozen: tuple[FrozenUnit, ...] = FROZEN_UNITS
) -> list[Unit]:
    """Đọc các bài đóng băng theo đúng thứ tự danh sách, dừng nếu bài biến mất hoặc đổi chữ.

    Bài sửa trên Threads hay có thêm post viết tiếp đều làm đổi `full_text`, và 2 vị trí đáp án
    tính trên chữ cũ sẽ lệch mà không báo lỗi, nên phải dừng ở đây để Thy quyết (ADR-0037, xem lại
    khi 5). Kiểm cả độ dài để số lưu sẵn mà CI dùng không thể lệch với bài thật.

    Không bắt được bài gốc xoá trên Threads: ingest chỉ ghi thêm nên hàng cũ còn nguyên trong DB.
    Phép so với bài còn sống là `live_mismatches` (lệnh `live-check` của bước dựng).
    """
    units: list[Unit] = []
    for expected in frozen:
        row = conn.execute(
            "SELECT full_text, continuation_ids_json FROM content_units WHERE id = ?",
            (expected.id,),
        ).fetchone()
        if row is None:
            raise CorpusChangedError(f"{expected.id}: không còn trong content_units")
        full_text = row[0]
        if len(full_text) != expected.length:
            raise CorpusChangedError(f"{expected.id}: độ dài full_text khác lúc đóng băng")
        if content_hash(full_text) != expected.sha256:
            raise CorpusChangedError(f"{expected.id}: full_text đã đổi so với lúc đóng băng")
        post_ids = [expected.id, *json.loads(row[1])]
        units.append(
            Unit(
                id=expected.id,
                full_text=full_text,
                posts=_post_spans(conn, expected.id, post_ids, full_text),
            )
        )
    return units


def live_mismatches(units: Sequence[Unit], live_texts: Mapping[str, str]) -> list[str]:
    """So các bài đóng băng với bài đang sống trên Threads; trả danh sách vấn đề (rỗng = khớp).

    `live_texts` là mã post → chữ, lấy từ danh sách post + reply của kênh lúc chạy (cùng endpoint
    ingest dùng). Post không có trong danh sách coi là đã xoá hoặc bị ẩn: bài demo phải là bài
    người đọc còn mở được. Bài gốc kiểm riêng, vì bài gốc không có chữ (chỉ ảnh) không nằm trong
    `posts`; post viết tiếp không có chữ thì không được kiểm (xoá nó không đổi chữ hay chunk nào,
    bài vẫn mở được qua bài gốc). Chữ của các post trong `posts` ghép bằng dấu cách phải ra đúng
    hash lúc đóng băng; một post bị làm rỗng trên Threads cũng làm lệch hash. Thông báo chỉ ghi mã
    bài, không ghi chữ bài.
    """
    problems: list[str] = []
    for unit in units:
        ids = dict.fromkeys([unit.id, *(post.post_id for post in unit.posts)])
        gone = [post_id for post_id in ids if post_id not in live_texts]
        if gone:
            problems.append(f"{unit.id}: post không còn trên Threads: {', '.join(gone)}")
            continue
        live = " ".join(live_texts[post.post_id] for post in unit.posts)
        if content_hash(live) != content_hash(unit.full_text):
            problems.append(f"{unit.id}: chữ trên Threads khác lúc đóng băng")
    return problems
