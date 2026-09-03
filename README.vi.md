# Threads AI Content

**Ngôn ngữ:** [English](README.md) · Tiếng Việt · [Français](README.fr.md)

![Status](https://img.shields.io/badge/status-Phase%201%20in%20progress-orange)
![Tests](https://img.shields.io/badge/tests-183%20passing-brightgreen)
![License](https://img.shields.io/badge/license-private-lightgrey)

> The algorithm, read back to you.
> (Thuật toán, được đọc ngược lại cho bạn.)

Thuật toán xếp hạng của Threads là một hộp đen — creator không có cách nào truy vấn tại sao bài này
"nổ" còn bài kia thì không. Dự án này chọn đúng 1 kênh Threads thật, **[@thydilammuon](https://www.threads.net/@thydilammuon)**
(một người Việt đang sống tại Pháp, chia sẻ về alternance, xin việc, và cuộc sống người Việt xa xứ),
làm case study thật: mọi con số trên dashboard đều được tính từ một công thức đã ghi chép rõ ràng,
có nguồn tham khảo — không bao giờ là một điểm số "hộp đen".

Đây là một **công cụ nội bộ, dùng riêng cho 1 kênh** — vừa để phân tích hiệu suất thật, vừa (sắp
tới) để generate content — được xây dựng đồng thời làm sản phẩm portfolio cho vị trí NLP/ML
Engineer. Không phải SaaS, không multi-tenant, và không có tham vọng trở thành vậy.

---

## Ảnh chụp màn hình

> 3 ảnh bên dưới đang trỏ tới `docs/screenshots/` nhưng **chưa được commit** — repo này private và
> cần chụp thật từ phiên `npm run dev` đang chạy trước khi push lần đầu. Xem mục
> [Chạy thử ở local](#chạy-thử-ở-local).

| Landing / story page | Overview — Timeline Brush | Analytics — phân tích theo múi giờ |
|---|---|---|
| ![Landing page](docs/screenshots/landing.png) | ![Overview dashboard](docs/screenshots/overview.png) | ![Analytics tab](docs/screenshots/analytics.png) |

---

## Mục lục

- [Vấn đề](#vấn-đề)
- [Giải pháp](#giải-pháp)
- [Tech stack](#tech-stack)
- [Kiến trúc](#kiến-trúc)
- [Điểm nhấn về methodology](#điểm-nhấn-về-methodology)
- [Trạng thái dự án](#trạng-thái-dự-án)
- [Chạy thử ở local](#chạy-thử-ở-local)
- [Về kênh](#về-kênh)
- [Giấy phép](#giấy-phép)

---

## Vấn đề

Threads chỉ cho creator đủ data để đưa ra quyết định *nghe có vẻ chắc chắn* nhưng thực ra không có
căn cứ.

- **Không có analytics đủ sâu.** Insights của Threads chỉ có `views`, `likes`, `replies`,
  `reposts`, `quotes` — không có impressions, không có reach, không có breakdown theo múi giờ.
  Creator chỉ còn cách đoán.
- **Không có insight ở cấp độ chủ đề.** Mỗi bài đăng được đánh giá độc lập. Không có cách nào sẵn
  có để thấy chủ đề nào, kể theo cách nào, thực sự hiệu quả hơn xuyên suốt lịch sử thật của kênh.
- **Báo cáo số liệu không trung thực về mặt thống kê.** 1 bài viral kéo mean lệch hẳn khỏi mức 1
  bài "bình thường" trông như thế nào, và 1 bucket "giờ đăng tốt nhất" chỉ có 2 bài lại được báo
  cáo với độ tự tin y hệt 1 bucket có 50 bài.

## Giải pháp

3 tầng, xây và verify đúng theo thứ tự đó — mỗi tầng đều bám vào methodology có trích dẫn, không
phải cảm tính.

| Tầng | Trạng thái | Làm gì |
|---|---|---|
| **Statistics layer** | Đã có | 6 index tách biệt — popularity, engagement, virality, conversation, velocity, longevity — không bao giờ gộp lại thành 1 điểm số duy nhất. Median luôn đi kèm mean (không bao giờ chỉ báo mean 1 mình), mọi bucket đều có IQR + cờ cảnh báo cỡ mẫu nhỏ, dùng Mann-Whitney U + Cliff's delta cho mọi so sánh nhóm, virality tính theo percentile riêng của từng kênh thay vì 1 ngưỡng cố định tùy tiện. |
| **NLP layer** | Đã có | Embedding đa ngôn ngữ (content trộn tự nhiên VI/FR/EN nên không dùng tokenizer riêng cho 1 ngôn ngữ) đưa vào UMAP + HDBSCAN để tự động khám phá chủ đề (unsupervised), sau đó Claude gán tên tiếng Anh cho từng cluster tìm được. Code-Mixing Index — một điểm số liên tục, không phải cờ boolean — đo mức độ 1 bài thực sự chuyển đổi ngôn ngữ. |
| **Generative AI + RAG** | Sắp có | Claude đã gán tên cho các cluster chủ đề. Tầng tiếp theo sẽ draft ý tưởng content mới, dựa trên retrieval trên chính những bài hiệu suất cao nhất của kênh, giữ đúng giọng văn thật của tác giả — không phải giọng AI chung chung. |

## Tech stack

Liệt kê đúng trạng thái thật của code hiện tại — không hứa hẹn tính năng chưa tồn tại.

| Layer | Công nghệ | Trạng thái |
|---|---|---|
| Backend / API | FastAPI | Đã có |
| Package manager | uv (`pyproject.toml` + `uv.lock`) | Đã có |
| Threads API client | httpx (async) | Đã có |
| Validation | Pydantic v2 | Đã có |
| AI / LLM | Claude API (`claude-opus-5`, gán tên cluster + prompt caching) | Đã có |
| Dashboard | Next.js 16 + Tailwind v4 + Recharts | Đã có |
| Database | SQLite (dev) → PostgreSQL (dự kiến trước khi có nhiều user) | Đã có (dev) |
| Metric scoring | Kiến trúc 6 index (popularity/engagement/virality/conversation/velocity/longevity) | Đã có |
| Language ID | lingua-py + Code-Mixing Index | Đã có |
| NLP feature extraction | sentence-transformers, đa ngôn ngữ (bge-m3 / multilingual-e5-large) | Đã có |
| Topic discovery | UMAP + HDBSCAN (clustering không giám sát) | Đã có |
| Code quality | ruff (lint+format), mypy (strict), pytest, pre-commit | Đã có |
| Fixed-category classification | SVM-RBF + Logistic Regression | Sắp có |
| Vector store / RAG | Chroma hoặc FAISS (tái dùng embedding của clustering) | Sắp có |
| Image generation | Pillow + font Google Sans (template carousel đã có, code chưa) | Sắp có |

## Kiến trúc

```
threads-ai-content/
├── src/
│   ├── api/            Client Threads Graph API (auth, pagination, caching) — đã có
│   ├── models/          Domain model ContentUnit / InsightSnapshot — đã có
│   ├── processing/       Ghép lại thread (root + chuỗi self-reply), làm sạch text — đã có
│   ├── analysis/         Metric 6-index + thống kê theo cửa sổ thời gian (median/mean/IQR) — đã có
│   ├── nlp/              Language ID, embedding đa ngôn ngữ, clustering UMAP+HDBSCAN — đã có
│   ├── db/                Schema SQLite (posts, content_units, insights_snapshots, topics) — đã có
│   ├── pipeline/           Ingest, cron snapshot 4h, cầu nối clustering Windows↔WSL2 — đã có
│   ├── generation/         Generate text bằng RAG — chưa bắt đầu
│   ├── carousel/           Ghép ảnh carousel bằng Pillow — chưa bắt đầu
│   ├── main.py             Entry point FastAPI — đã có
│   └── dashboard/          App Next.js: landing page + Overview/Analytics/Topic Explorer — đã có
└── tests/                183 test, ruff + mypy strict sạch
```

Luồng dữ liệu, từ đầu tới cuối:

```
Threads Graph API  ──(cron 4h)──>  SQLite  ──>  FastAPI  ──>  Dashboard Next.js
        │                              │
        └── posts, replies,            └── Pipeline NLP (WSL2: embedding, UMAP, HDBSCAN)
            views theo ngày                cluster lại mỗi ngày, Claude gán tên cluster
```

Pipeline ML batch (embedding, clustering) chạy như 1 job riêng, ghi kết quả vào SQLite — FastAPI
chỉ đọc kết quả đã tính sẵn, không bao giờ load model transformer mỗi request.

## Điểm nhấn về methodology

Một vài quyết định dự án coi là nền tảng, tài liệu đầy đủ tại
[`docs/claude/architecture.md`](docs/claude/architecture.md) và
[`docs/claude/data-model.md`](docs/claude/data-model.md):

- **Median làm số liệu chính, mean là số phụ — không bao giờ dùng tỉ lệ pooled.** Một tỉ lệ
  Σinteractions/Σviews gộp cho cả cửa sổ thời gian sẽ bị chi phối bởi bài có views cao nhất; median
  giữa các bài luôn được báo cáo trước, kèm mean, cỡ mẫu (`n`), và IQR đi cùng.
- **6 index riêng biệt, không bao giờ gộp thành 1 điểm.** Popularity, engagement, virality,
  conversation, velocity, longevity trả lời những câu hỏi khác nhau và không bao giờ bị trung bình
  hoá lại thành 1 "điểm số" duy nhất.
- **Mọi hằng số heuristic đều được suy ra từ data thật, hoặc ghi rõ là giả thuyết chưa calibrate**
  — không có con số "ma thuật" nào không ghi chú nguồn gốc.
- **Không gian clustering được chọn bằng thực nghiệm, không phải lý thuyết suông.** HDBSCAN được
  thử cả trên không gian embedding gốc 1024 chiều lẫn không gian đã giảm chiều bằng UMAP —
  embedding gốc bị suy biến (1 cluster chiếm 82% dữ liệu), không gian UMAP cho cluster ổn định và
  cân đối hơn — kết quả thực nghiệm ghi đè lên giả định thiết kế ban đầu. Số liệu đầy đủ tại
  `data-model.md`.
- **Code-mixing là 1 điểm số liên tục, không phải boolean.** Theo đúng literature NLP về
  code-switching, language ID ở cấp document trên văn bản ngắn không đáng tin cậy và không nên
  dùng để "gate" các bước xử lý phía sau — Code-Mixing Index đo *mức độ* 1 bài trộn ngôn ngữ thay
  vì phân loại nhị phân.

## Trạng thái dự án

**Phase 1 — công cụ phân tích + content cho 1 kênh (đang triển khai).** Client Threads API,
pipeline NLP khám phá chủ đề, kiến trúc metric 6-index, thống kê theo cửa sổ thời gian, dashboard
3 tab (Overview, Analytics, Topic Explorer) cộng landing page này — tất cả đã chạy thật trên data
production (183 test pass, ruff + mypy strict sạch). AI content generation (`src/generation/`) và
export ảnh carousel (`src/carousel/`) đã thiết kế nhưng chưa xây.

**Phase 2 — nghiên cứu hệ sinh thái Threads / "KOL Strategy Engine" (định hướng, chưa cam kết).**
Mở rộng từ 1 kênh sang nghiên cứu pattern trên nhiều tài khoản cần Meta Advanced Access (Business
Verification, App Review) — dự án hiện chưa có và cũng chưa cần cho Phase 1. Chưa cam kết timeline
hay effort kỹ thuật nào — xem đầy đủ lý do tại [`CLAUDE.md`](CLAUDE.md).

## Chạy thử ở local

```bash
# Backend (Python 3.12 qua uv)
pip install --user uv
uv sync
cp .env.example .env               # điền THREADS_* và ANTHROPIC_API_KEY
uv run pytest -q                   # 183 test
uv run uvicorn src.main:app --reload --port 8000

# Dashboard (Next.js)
cd src/dashboard
npm install
npm run dev                        # http://localhost:3000
```

Dashboard đọc data thật từ backend FastAPI ở trên — cần chạy cả 2 cùng lúc mới thấy số liệu thật.

## Về kênh

Xây dựng bởi Thy ([@thydilammuon](https://www.threads.net/@thydilammuon)), một người Việt đang
sống và làm việc tại Pháp, chia sẻ về alternance, xin việc, và cuộc sống thường ngày của người Việt
xa xứ. Dự án bắt đầu như một cách để thực sự hiểu chính kênh của mình — không phải vanity metrics,
mà là một cái nhìn nghiêm túc về việc bài đăng thật của mình đang hoạt động ra sao — và phát triển
thành case study thống kê + NLP đầy đủ như mô tả ở trên.

## Giấy phép

Dự án cá nhân, private. Giữ toàn bộ quyền — không phải mã nguồn mở, không nhận contribution từ bên
ngoài. Được xây dựng làm sản phẩm portfolio, thể hiện năng lực kỹ thuật NLP/ML áp dụng thật trên
data production.
