"""Stopword cho TỪ KHOÁ topic (c-TF-IDF, `src/nlp/topic_profile.py`) — ADR-0022.

Chỉ dùng ở bước chọn từ khoá, SAU khi đã embed + gom cụm (như BERTopic lọc ở vectorizer):
embedding, cụm, tên topic không đổi (`.claude/rules/nlp-research.md`: không xoá stop word
trước embedding).

Lựa chọn thiết kế, KHÔNG phải danh sách chuẩn ngành: không tìm thấy tài liệu nào hướng dẫn
stopword cho topic modelling trên mạng xã hội tiếng Việt trộn Pháp/Anh. Đã đo 2026-10-08
trên 9 cụm thật và loại 2 nguồn có sẵn:
- `stopwords/vietnamese-stopwords` (MIT, 1.942 dòng): chứa cả cụm có nghĩa ("thời gian",
  âm tiết của "phỏng vấn", "chia sẻ") → làm vỡ từ ghép; lại thiếu teencode ("tui", "ko",
  "hông", "nha").
- `stopwords-iso` fr/en (MIT): trùng âm tiết Việt / từ mượn có nghĩa trên kênh ("du" của
  "du học", "eu", "vn", "cv", "ta", "an") → xoá từ khoá thật.
Vì vậy danh sách dưới đây nhỏ, chia nhóm có nhãn, chỉ gồm từ không mang chủ đề. Từ đa nghĩa
("sao", "bao", "họ", "từ") chỉ bị bỏ khi đứng RIÊNG là 1 từ — trong từ ghép ("ngôi_sao",
"từ_vựng") chúng được giữ. Thêm/bớt mục → đo lại từ khoá trước/sau (ADR-0022, "Xem lại khi").
"""

from __future__ import annotations

from typing import Final

# Từ chức năng tiếng Việt: lượng từ, giới từ, liên từ, phó từ, trợ từ cuối câu
FUNCTION_WORDS: Final = frozenset(
    {
        "một", "mấy", "điều", "các", "những", "của", "là", "và", "với", "thì", "mà", "cho", "để",
        "được", "này", "đó", "kia", "khi", "rất", "cũng", "đã", "đang", "sẽ", "có", "không",
        "bị", "từ", "ra", "vào", "lên", "xuống", "trong", "tại", "theo", "nên", "vì", "nếu",
        "như", "hay", "hoặc", "nhưng", "còn", "lại", "thêm", "nữa", "luôn", "vẫn", "chỉ",
        "đều", "cả", "mỗi", "nào", "gì", "sao", "đâu", "bao", "vậy", "thế", "rồi", "ạ", "nhé",
        "ơi", "à", "á",
        # "thể" đứng riêng hầu như luôn là mảnh của "có thể"/"không thể" bị tách rời
        "thể",
    }
)  # fmt: skip

# Từ chức năng GHÉP (trạng từ/liên từ 2 âm tiết) — bộ tách từ ghép chúng thành 1 từ ("có_thể"),
# nên phải liệt kê nguyên cụm; số lần xuất hiện 2026-10-08 trên 146 bài: "có thể" 139,
# "thậm chí" 37, "thật ra" 29
FUNCTION_COMPOUNDS: Final = frozenset(
    {
        "có thể", "tất cả", "thật ra", "thậm chí", "nhất là", "vì vậy", "bởi vì", "tuy nhiên",
        "ngoài ra", "như vậy", "hiện tại", "đặc biệt", "cụ thể", "hoàn toàn", "thực sự",
        "làm sao", "gọi là", "không chỉ", "không thể", "không những", "không thể nào",
    }
)  # fmt: skip

# Đại từ xưng hô — trên kênh này chúng có mặt ở hầu hết chủ đề, không nói chủ đề là gì.
# Cố ý KHÔNG có "anh": trùng "tiếng Anh" (kênh nói nhiều về IELTS/tiếng Anh). Đo 2026-10-08: "anh"
# có mặt ở 7/9 cụm (dưới ngưỡng 80% của `MAX_CLUSTER_SHARE_FOR_KEYWORD`) nhưng không vào top-8 topic
# nào — IDF theo cụm đã hạ điểm nó
PRONOUNS: Final = frozenset(
    {
        "tui", "tớ", "mình", "tôi", "toi", "bạn", "em", "chị", "các em", "mọi người",
        "mn", "mng", "người ta", "họ", "nó", "anh ấy", "chị ấy", "anh chị em",
    }
)  # fmt: skip

# Teencode / viết tắt / tiểu từ mạng (đếm 2026-10-08 trên 146 bài: "nha" 62, "tui" 26,
# "hông" 23, "ko" 19, "hổng" 15, "mn" 15, "vs" 15, "đc" 9, "nè" 9, "nhen" 7, "nh" 7)
INFORMAL: Final = frozenset(
    {"ko", "k", "hông", "hổng", "nha", "nè", "nhen", "nh", "vs", "đc", "dc", "huhu", "hihi", "ha"}
)

# Từ chức năng tiếng Pháp KHÔNG trùng âm tiết Việt có nghĩa — cố ý bỏ "du", "la", "en", "ta"…
FRENCH_FUNCTION_WORDS: Final = frozenset(
    {"de", "des", "le", "les", "et", "un", "une", "pour", "avec", "dans", "sur", "au", "aux", "est"}
)

# Từ chức năng tiếng Anh không trùng âm tiết Việt (cố ý bỏ "to", "in", "an"…)
ENGLISH_FUNCTION_WORDS: Final = frozenset(
    {"the", "and", "for", "of", "with", "you", "is", "are", "this", "that"}
)

KEYWORD_STOPWORDS: Final = (
    FUNCTION_WORDS
    | FUNCTION_COMPOUNDS
    | PRONOUNS
    | INFORMAL
    | FRENCH_FUNCTION_WORDS
    | ENGLISH_FUNCTION_WORDS
)

# Nhóm "dính keo": bộ tách từ (model báo chí) hay dính chúng vào mép từ bên cạnh ("tệ_nha",
# "ko_tệ") — được bóc ở mép từ ghép, THEO HƯỚNG vì nhiều mục cũng là âm tiết thật ("nha_sĩ",
# "lỗ_hổng", "bên_hông"). KHÔNG gồm từ chức năng/đại từ tiếng Việt: chúng là âm tiết của từ
# ghép có nghĩa ("điều_kiện", "chuẩn_bị", "từ_chối", "thế_giới") — bóc sẽ ra mảnh.
# Tiểu từ cuối câu: chỉ bóc ở mép PHẢI ("đắt_nha" → "đắt"; "nha_sĩ", "nha_khoa" giữ)
GLUE_RIGHT_EDGE: Final = frozenset({"nha", "nè", "nhen", "ha", "hihi", "huhu"})
# Còn lại bóc ở cả 2 mép — gồm "ko"/"hông"/"hổng": đo 2026-10-08 trên 146 bài, 8/8 lần chúng dính
# ở mép phải là tiểu từ hỏi ("ngon_hông" = "ngon không?"), không lần nào là từ thật
GLUE_BOTH_EDGES: Final = (
    (INFORMAL - GLUE_RIGHT_EDGE) | FRENCH_FUNCTION_WORDS | ENGLISH_FUNCTION_WORDS
)
# Từ ghép có âm tiết "dính keo" ở mép mà vẫn là 1 từ — không bóc. Đã thấy trên kênh: "Tây Ban
# Nha" (2 bài), "Bồ Đào Nha" (1 bài); "bên hông", "lỗ hổng" là từ thật (chưa gặp, giữ phòng)
PROTECTED_COMPOUNDS: Final = frozenset({"tây_ban_nha", "bồ_đào_nha", "bên_hông", "lỗ_hổng"})
