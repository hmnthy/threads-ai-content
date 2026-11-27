// Chữ và hàm phụ của trang /rag-pipeline bản đầu (Thy chốt 2026-11-12: 3 khối + khối Loading và bản đồ pipeline thêm sau, chỉ component có sẵn — phạm vi ở
// `docs/design/ui-contract-audit.md`, mục "`/rag-pipeline` — trang bản đầu thu hẹp"). Chữ hiển thị là bản nháp,
// copy-reviewer đọc rồi Thy duyệt. File thường (không "use client") để server component import được.
import { PENDING_CONTEXT, PENDING_TRANSFORMED } from "./ragDemo/demoFile.ts";
import type { DemoFile, Question, Way } from "./ragDemo/demoFile.ts";
import type { Outcome } from "./ragDemo/answer.ts";
import { cosineOf } from "./ragDemo/filters.ts";
import type { Rerank } from "./ragDemo/rerank.ts";
import type { Retriever, RetrievalStatus } from "./ragDemo/retrieve.ts";

// Một nguồn cho dải mục lục đầu trang và nhãn trên tiêu đề mỗi khối (như `topicSections.ts`)
// Thy 2026-11-12 (phương án A): thêm khối Loading đứng đầu — bước đầu của pipeline trong repo mẫu (Loader)
// Thy 2026-11-12: thêm bản đồ pipeline đứng đầu — đối chiếu từng bước với chuẩn repo mẫu của thầy Thy
// PR 2a (Thy chốt 2026-11-25): thêm bảng thuật ngữ đứng cuối, như khối 06 của /topics
// PR 2b (thẻ Thy duyệt 2026-11-26): khối Chunking riêng ngay sau Loading — bước 2 của repo mẫu. Chữ trên trang gọi số
// khối qua `ragNumber`, không viết tay, để chèn khối không làm lệch lời dẫn
export const RAG_SECTIONS = [
  ["pipeline", "01", "Pipeline map"],
  ["loading", "02", "Loading"],
  ["chunking", "03", "Chunking"],
  ["embedding", "04", "Embedding"],
  ["question", "05", "Question"],
  ["passages", "06", "Ranked passages"],
  ["about", "07", "About this demo"],
  ["terms", "08", "Terms"],
] as const;

// Bản đồ pipeline: các bước theo đúng số + tên của repo mẫu (README vietnh1009/RAG-pipeline-visualizer, đọc
// 2026-11-12 — repo không có bước 5–6), trạng thái của từng bước trên trang bản đầu (bảng đối chiếu ở
// `docs/design/ui-contract-audit.md`, mục "`/rag-pipeline` — trang bản đầu thu hẹp")
export type StepStatus = "on-page" | "fixed" | "later" | "left-out";
export const STEP_STATUS_SHOWN: Record<StepStatus, { mark: string; name: string; rule: string }> = {
  // 3 reviewer 2026-11-12: "on-page" chỉ cho bước có thiết lập làm đổi bảng xếp hạng (khoá trong `Settings`)
  "on-page": { mark: "●", name: "On this page", rule: "change this step’s setting and the ranking updates." },
  fixed: {
    mark: "◐",
    name: "Fixed choice",
    rule: "the step runs with one fixed choice, in advance or in your browser; the linked block shows or explains it, with no setting to change.",
  },
  later: { mark: "○", name: "Later version", rule: "not on the page yet; the step’s text says what is already prepared." },
  "left-out": { mark: "×", name: "Left out on purpose", rule: "this demo stops before any answer is written." },
};

export type PipelineStep = {
  number: number;
  name: string;
  stage: "indexing" | "generation";
  optional: boolean;
  status: StepStatus;
  block: (typeof RAG_SECTIONS)[number][0] | null; // khối của trang chứa bước này
  what: string;
};

export const PIPELINE_STEPS: readonly PipelineStep[] = [
  {
    number: 1,
    name: "Loader",
    stage: "indexing",
    optional: false,
    status: "fixed",
    block: "loading",
    what: "Turns the source into documents. Here the source is the channel’s Threads posts, and one document is one content unit.",
  },
  {
    number: 2,
    name: "Chunking",
    stage: "indexing",
    optional: false,
    status: "on-page",
    block: "chunking",
    // RAG PR 3a: bỏ câu trạng thái dense ("not computed yet") — chi tiết ở khối 03, theo file đang đọc
    what: "Cuts each content unit into passages, with 7 methods to choose from, and can add a context sentence (a short note on where the passage sits in its content unit) to every passage that is not the whole content unit, before it is indexed.",
  },
  {
    number: 3,
    name: "Embedding",
    stage: "indexing",
    optional: false,
    status: "fixed",
    block: "embedding",
    // copy-reviewer 2026-11-12: "BM25 needs no vectors" dễ bị bắt bẻ — BM25 vẫn là một vector thưa (đếm từ)
    // PR 2b: khối Embedding riêng; BM25 dựng lại cả khi bật / tắt câu ngữ cảnh (copy-reviewer PR 2b vòng 1)
    what: "Dense: OpenAI text-embedding-3-small vectors, made before publishing; the page shows how similar the content units and passages are to each other. Sparse: BM25 represents a passage by its word counts instead of a learned vector; those counts are rebuilt in your browser for the chunking and context-sentence setting you pick.",
  },
  {
    number: 4,
    name: "Vector DB",
    stage: "indexing",
    optional: false,
    status: "fixed",
    block: "about",
    what: "Replaced by precomputed scores, so there is no vector database: the similarity between every question and every passage is computed in advance and shipped in one file, and the BM25 index lives in your browser. For a small, frozen set of content units and fixed questions, that is enough (a design choice).",
  },
  {
    number: 7,
    name: "Pre-retrieval",
    stage: "generation",
    optional: true,
    status: "later",
    block: null,
    // RAG PR 3a commit 2: điểm dense của câu biến đổi đã tính (file định dạng 3); khối riêng ở commit 3
    what: "Rewriting the question before searching (rewrite, expand, HyDE, multi-query, decompose, step-back). The rewrites are stored, but this version still searches with the original question.",
  },
  {
    number: 8,
    name: "Retrieval",
    stage: "generation",
    optional: false,
    status: "on-page",
    block: "passages",
    what: "Finds candidate passages with BM25, dense similarity or both fused with RRF. Two other fusion methods (weighted, DBSF) come in a later version.",
  },
  {
    number: 9,
    name: "Post-retrieval",
    stage: "generation",
    optional: true,
    status: "on-page",
    block: "passages",
    what: "Reranks the top passages with a cross-encoder or Claude Haiku. Filters, diversity (MMR) and a before/after view come in a later version.",
  },
  {
    number: 10,
    name: "Prompt",
    stage: "generation",
    optional: false,
    status: "left-out",
    block: null,
    what: "No prompt is built: this demo is meant to show retrieval, and a written answer would hide what retrieval did.",
  },
  {
    number: 11,
    name: "Generation",
    stage: "generation",
    optional: false,
    status: "left-out",
    block: null,
    what: "No answer is written by a model. The page stops at the ranked source passages, which is what an answer would be built from.",
  },
];

export function ragNumber(id: (typeof RAG_SECTIONS)[number][0]): string {
  return RAG_SECTIONS.find(([key]) => key === id)![1];
}

// Tứ phân vị kiểu `statistics.quantiles(n=4, method="inclusive")` của `src/analysis/stats.py` (một cách tính IQR
// cho cả sản phẩm): nội suy tuyến tính tại vị trí (n − 1) · p trên dãy đã sắp xếp
export function quartiles(values: readonly number[]): { q1: number; median: number; q3: number } {
  const sorted = [...values].sort((a, b) => a - b);
  const at = (p: number) => {
    const pos = (sorted.length - 1) * p;
    const lo = Math.floor(pos);
    const hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  };
  return { q1: at(0.25), median: at(0.5), q3: at(0.75) };
}

// Độ dài theo ký tự người đọc thấy (điểm mã Unicode, như `len()` của Python) — `.length` của JS đếm đơn vị UTF-16
export function characterCount(text: string): number {
  return Array.from(text).length;
}

// Cỡ đoạn của một cách chia (khối Chunking, PR 2b — Thy chọn D3 2026-11-26: bảng 7 dòng, không histogram). Độ dài =
// `characterCount` của chữ đoạn (cùng đơn vị với bộ chia `src/rag_demo/chunking.py`, đếm điểm mã). `lengths` null khi
// cách chia không có đoạn nào: trang hiện "—", không in median của tập rỗng (luật dashboard). `withContext` = số đoạn có
// câu ngữ cảnh — đoạn trùng cả bài (bài ngắn hơn cửa sổ, thread 1 post) không có câu nào (`src/rag_demo/demo_file.py`)
export type ChunkStats = {
  count: number;
  withContext: number;
  lengths: { q1: number; median: number; q3: number; min: number; max: number } | null;
};

export function chunkStats(demo: DemoFile, way: Way): ChunkStats {
  const passages = demo.ways[way].map((chunk) => demo.passages[chunk.passage]);
  const lengths = passages.map((passage) => characterCount(passage.text));
  const withContext = passages.filter((passage) => passage.context !== null).length;
  if (lengths.length === 0) return { count: 0, withContext, lengths: null };
  return {
    count: lengths.length,
    withContext,
    lengths: { ...quartiles(lengths), min: Math.min(...lengths), max: Math.max(...lengths) },
  };
}

// Khối Embedding (PR 2b, Thy chọn D1 2026-11-26): heatmap cosine giữa các bài (cách "whole") + láng giềng gần của 1 đoạn.
// Cosine đọc từ file (`cosine[way]`, tam giác trên theo hàng, thứ tự mã chunk — `cosineOf`), không tính lại.
export type CosinePair = { value: number; a: number; b: number }; // a < b: mã chunk của cách chia
export type CosineSpread = { pairs: number; q1: number; median: number; q3: number; low: CosinePair; high: CosinePair };

// Phân bố cosine mọi cặp đoạn khác nhau của một cách chia; null khi < 2 đoạn (không có cặp nào). Hoà ở cặp thấp / cao
// nhất → cặp đứng trước theo thứ tự hàng (mã chunk nhỏ hơn) — một luật, để câu chữ không đổi giữa hai lần dựng trang
export function cosineSpread(demo: DemoFile, way: Way): CosineSpread | null {
  const n = demo.ways[way].length;
  const values = demo.cosine[way];
  if (n < 2 || values.length === 0) return null;
  let low: CosinePair | null = null;
  let high: CosinePair | null = null;
  let k = 0;
  for (let a = 0; a < n; a += 1) {
    for (let b = a + 1; b < n; b += 1) {
      const value = values[k];
      if (low === null || value < low.value) low = { value, a, b };
      if (high === null || value > high.value) high = { value, a, b };
      k += 1;
    }
  }
  return { pairs: values.length, ...quartiles(values), low: low!, high: high! };
}

// Mọi cặp đoạn khác nhau của một cách chia, cosine cao nhất trước; hoà → cặp đứng trước theo thứ tự hàng (a rồi b) —
// bảng "Show as table" của heatmap (Thy chọn 2026-11-27: lối vào bàn phím / trình đọc màn hình như /analytics)
export function cosinePairs(demo: DemoFile, way: Way): CosinePair[] {
  const n = demo.ways[way].length;
  const values = demo.cosine[way];
  const pairs: CosinePair[] = [];
  let k = 0;
  for (let a = 0; a < n; a += 1) {
    for (let b = a + 1; b < n; b += 1) {
      if (k < values.length) pairs.push({ value: values[k], a, b });
      k += 1;
    }
  }
  return pairs.sort((x, y) => y.value - x.value || x.a - y.a || x.b - y.b);
}

// Số láng giềng gần hiện cho một đoạn: lựa chọn thiết kế (Thy D1: "top-5"), không có bằng chứng tối ưu
export const NEIGHBOURS = 5;

// `count` đoạn có cosine cao nhất với đoạn `chunk` (không tính chính nó); cosine bằng nhau → đoạn đứng trước theo mã
// chunk (sắp xếp ổn định trên thứ tự mã)
export function nearestPassages(
  demo: DemoFile,
  way: Way,
  chunk: number,
  count: number,
): { chunk: number; cosine: number }[] {
  const n = demo.ways[way].length;
  const others: { chunk: number; cosine: number }[] = [];
  for (let other = 0; other < n; other += 1) {
    if (other !== chunk) others.push({ chunk: other, cosine: cosineOf(demo, way, chunk, other) });
  }
  return others.sort((x, y) => y.cosine - x.cosine || x.chunk - y.chunk).slice(0, count);
}

// Cosine hiện trên trang: 3 chữ số (file lưu 6 — Method nói rõ)
export function cosineText(value: number): string {
  return value.toFixed(3);
}

// Bộ tìm thật sự xếp danh sách: "hybrid rơi về BM25" (câu ngữ cảnh có hiệu lực, dense còn chờ — ADR-0041 Luật chung 8)
// chỉ còn BM25, nên tên điểm trên mỗi dòng phải là "BM25 score", không phải "RRF score"
export function rankedBy(retriever: Retriever, status: RetrievalStatus): Retriever {
  return retriever === "hybrid" && status === "bm25-only" ? "bm25" : retriever;
}

// Chữ của công tắc câu ngữ cảnh (UI-0039-chunking-options: tắt ở "không chia", kèm một câu vì sao) và của 2 trạng thái
// "in progress" ở khối kết quả (UI-0041-step-order cột E). Bản nháp: copy-reviewer đọc, Thy duyệt.
export const CONTEXT_SHOWN = {
  off: "Off: each passage is searched as it is.",
  whole:
    "Not available with No chunking: each passage is already a whole content unit, so there is nothing around it to describe.",
} as const;

// Phần còn chờ của file đang đọc (RAG PR 3a): định dạng 2 (bản trên Blob tới lần publish kế tiếp) còn 2 mục, định dạng
// 3 không mục nào. Chữ nói dense "chưa tính" chỉ hiện khi file thật sự còn mục đó — không viết cứng theo một bản file
export type Pending = { context: boolean; transformed: boolean };
export function pendingOf(demo: DemoFile): Pending {
  return {
    context: demo.provenance.pending.includes(PENDING_CONTEXT),
    transformed: demo.provenance.pending.includes(PENDING_TRANSFORMED),
  };
}

// Câu dưới công tắc khi bật. ux-reviewer + code-reviewer PR 2b vòng 1: đoạn trùng cả bài không có câu ngữ cảnh —
// không viết "each passage" trần
export function contextOnText(contextPending: boolean): string {
  const lead =
    "On: each passage is searched together with its context sentence, written in advance by Claude Haiku, that places the passage in its content unit; a passage that is the whole content unit has none.";
  return contextPending
    ? `${lead} Only BM25 uses it for now: dense similarity for passages with their context sentence is not computed yet.`
    : `${lead} Both BM25 and dense similarity use it.`;
}

// Ghi chú dưới "The passages of one content unit" theo số đoạn THẬT của bài đang chọn (code-reviewer PR 2b vòng 1, lỗi
// chặn: bài #13 chỉ có 1 đoạn = cả bài ở mọi cách trừ "No chunking", câu gán câu ngữ cảnh cho từng đoạn sai). Chỉ
// đoạn trùng cả bài mới không có câu ngữ cảnh, nên `withSentence` = 0 nghĩa là bài giữ nguyên một đoạn
// PR 2b commit 3: "No chunking" không cắt gì → không viết "Cut with No chunking" (NIT copy-reviewer); câu "mọi đoạn
// có câu" ghi bằng số đếm, không bằng cụm "each passage with …" (luật `ADR0039-every-passage-context`); động từ theo số
export function unitPassagesNote(way: Way, contextOn: boolean, withSentence: number, total: number): string {
  const lead = way === "whole" ? "Kept whole with No chunking" : `Cut with ${WAYS_SHOWN[way].label}`;
  if (!contextOn) return `${lead}.`;
  if (withSentence === 0) {
    return `${lead}. This content unit stays one passage, the whole unit, so it has no context sentence.`;
  }
  if (withSentence === total) {
    return total === 1
      ? `${lead}; its one passage has a context sentence, shown above it.`
      : `${lead}; all ${total} passages have a context sentence, shown above them.`;
  }
  return `${lead}; ${withSentence} of ${total} passages ${withSentence === 1 ? "has" : "have"} a context sentence, shown above ${withSentence === 1 ? "it" : "them"}.`;
}

// Câu trả lời của khối Chunking (3 reviewer PR 2b: "No chunking cuts the 19 content units…" tự mâu thuẫn). `median`
// null khi cách chia không có đoạn nào
export function chunkingAnswer(way: Way, units: number, passages: number, median: number | null): string {
  const name = WAYS_SHOWN[way].label;
  if (median === null) return `${name} gives no passages.`;
  const length = `with a median length of ${Math.round(median).toLocaleString("en-US")} characters`;
  return way === "whole"
    ? `No chunking keeps the ${units} content units whole: ${passages.toLocaleString("en-US")} passages, ${length}.`
    : `${name} cuts the ${units} content units into ${passages.toLocaleString("en-US")} passages, ${length}.`;
}

// Ghi chú của Key number "Passages ranked" theo bộ tìm THẬT SỰ xếp danh sách (`rankedBy`): khi Hybrid rơi về BM25,
// câu "dense similarity ranks every passage" đứng cạnh số của BM25 là sai (3 reviewer PR 2b)
export function rankedNote(ranker: Retriever): string {
  if (ranker === "bm25") return "BM25 leaves out passages that share no word with the question.";
  if (ranker === "dense") return "Dense similarity ranks every passage.";
  return "Hybrid ranks every passage: the dense list holds them all, and BM25 adds to those that share a word with the question.";
}

// Chú giải ¶ + nhãn chữ gốc câu ngữ cảnh: một câu đúng với MỌI bộ tìm (code-reviewer + ux-reviewer PR 3a commit 2,
// lỗi chặn: "BM25 searched it" / "(what BM25 searches)" sai khi chọn Dense, BM25 không chạy). Ở file định dạng 2 khi
// Hybrid rơi về BM25, "the search" là BM25 — vẫn đúng
export const CONTEXT_LEGEND =
  "shown above a passage when the context sentence is on, because the search reads the two together; a passage that is a whole content unit has none.";
export const CONTEXT_ORIGINAL_LABEL = "Context sentence, original language (read by the search together with the passage)";

// Method "Embedding" của khối 04 theo file đang đọc. Code-reviewer PR 3a commit 2 (lỗi chặn, lần 3 của cùng lỗi):
// không hứa câu ngữ cảnh cho mọi đoạn (luật `ADR0039-every-passage-context`) — đoạn trùng cả bài không có câu nào
// (ADR-0039 D2)
export function embeddingMethodText(model: string, pending: Pending): string {
  const extra = [
    pending.context ? null : "for each passage that has a context sentence, joined to that sentence",
    pending.transformed ? null : "for each text Claude Haiku wrote from a question to search with (rewrites, sub-questions, the HyDE answer)",
  ].filter((part): part is string => part !== null);
  const same = extra.length === 0 ? "" : ` The same was done ${extra.join(", and ")}.`;
  return `Every passage of every chunking method, and every question, was sent once to OpenAI ${model} through its API before the demo was published.${same} The vectors themselves are not in the demo file; only the cosines computed from them are.`;
}

// Chỉ hiện với file còn phần chờ (định dạng 2): `retrievalPlan` ra "in-progress" / "bm25-only" theo `pending` của file
export const IN_PROGRESS_SHOWN = {
  // "dense trần cần phần còn chờ": không có danh sách nào
  dense:
    "In progress: dense similarity for passages with their context sentence is not computed yet, so this setup has no ranking. Turn the context sentence off, or choose BM25.",
  // "hybrid rơi về BM25": các bước sau vẫn chạy trên danh sách BM25
  hybrid:
    "In progress — showing BM25 only: dense similarity for passages with their context sentence is not computed yet, so Hybrid ranks by BM25 alone.",
} as const;

export function ragShort(id: (typeof RAG_SECTIONS)[number][0]): string {
  return RAG_SECTIONS.find(([key]) => key === id)![2];
}

// Hiện tượng mỗi câu hỏi phô ra — bảng D10 của ADR-0037 (Thy duyệt 2026-11-05), dịch sang tiếng Anh. Mỗi mục là
// cụm danh từ đứng sau "Q{n} tests …" (copy-reviewer 2026-11-25: "tests one difficulty: …" sai ngữ pháp ở Q1, Q7,
// và Q3, Q7 có 2 khó khăn)
export const QUESTION_TESTS: Record<number, string> = {
  1: "a question typed without Vietnamese diacritics",
  2: "an answer that uses other words, partly in another language",
  3: "one question with several parts, whose answer needs 2 content units",
  // ADR-0040: bài bị xoá trên Threads sau mốc đóng băng là bài ĐĂNG TRƯỚC (18117744790996401, 2026-10-12); bài còn
  // lại đăng 2026-10-26 → còn 1 bài đáp án (Thy chốt ý 2026-11-25; 2 reviewer vòng 1: "the second copy" nói ngược)
  4: "near-duplicate posts, but the earlier of the two was deleted from Threads after the freeze, so only one answering content unit remains",
  5: "an answer that sits in a follow-up post of the thread",
  6: "a question asked in French about a post written in Vietnamese",
  7: "a vague question whose answer needs 2 content units",
  8: "a keyword trap: another post also talks about prices",
  9: "numbers and product names",
  10: "a question that no content unit answers",
};

// 7 cách chia (ADR-0039 D1): nhãn nút + một câu giải thích
export const WAYS_SHOWN: Record<Way, { label: string; sentence: string }> = {
  whole: { label: "No chunking", sentence: "Each content unit is one passage, however long." },
  post: { label: "One per post", sentence: "Each post of a thread is one passage." },
  fixed_300: {
    label: "Fixed 300",
    sentence: "Windows of 300 characters that overlap by 40, cut at a space.",
  },
  fixed_500: {
    label: "Fixed 500",
    sentence: "Windows of 500 characters that overlap by 60, cut at a space.",
  },
  fixed_800: {
    label: "Fixed 800",
    sentence: "Windows of 800 characters that overlap by 100, cut at a space.",
  },
  recursive_500: {
    label: "Recursive 500",
    sentence: "Split by paragraph, then by sentence, and merged back up to 500 characters.",
  },
  // ADR-0039 D1: ngưỡng 1/4 thấp nhất + trần 800 là lựa chọn thiết kế (reviewer 2026-11-12: hằng số thiếu nhãn)
  semantic: {
    label: "Semantic",
    sentence:
      "Cut between two sentences when their meanings are among the least similar quarter of all neighbouring pairs, at most 800 characters (both limits are design choices).",
  },
};

export const RETRIEVERS_SHOWN: Record<Retriever, string> = {
  bm25: "BM25 (keywords)",
  dense: "Dense (meaning)",
  hybrid: "Hybrid (both, fused)",
};

export const RERANKS_SHOWN: Record<Rerank, string> = {
  none: "No reranking",
  cross_encoder: "Cross-encoder",
  haiku: "Claude Haiku",
};

// Tên loại điểm của một dòng: bước chấm gần nhất của dòng đó (dòng "not reranked" giữ điểm bước trước)
export function scoreName(retriever: Retriever, rerank: Rerank, notReranked: boolean): string {
  if (rerank === "cross_encoder" && !notReranked) return "cross-encoder logit";
  if (rerank === "haiku" && !notReranked) return "Claude Haiku 5.5 score, 0–3";
  if (retriever === "bm25") return "BM25 score";
  if (retriever === "dense") return "cosine similarity";
  return "RRF score";
}

// Khoảng hạng: "3" hoặc "3–5" (hoà)
export function rankText(from: number, to: number): string {
  return from === to ? String(from) : `${from}–${to}`;
}

// Điểm hiện cạnh một dòng: điểm Haiku là số nguyên 0–3 (ADR-0041 Luật chung 3) → "3", không "3.000000"; điểm
// khác làm tròn 6 chữ số như lúc so hoà (`provenance.score_decimals`)
export function scoreText(score: number, rerank: Rerank, notReranked: boolean): string {
  return rerank === "haiku" && !notReranked ? String(Math.round(score)) : score.toFixed(6);
}

// Tên bước lọc như ADR-0041 ghi ("filtered out at: near-duplicate filter") — engine trả mã bước, không phải chữ
type FilterStep = Extract<Outcome, { kind: "filtered" }>["step"];
export const FILTER_SHOWN: Record<FilterStep, string> = {
  metadata: "metadata filter",
  "haiku-filter": "Haiku relevance filter",
  "near-duplicate": "near-duplicate filter",
};

// Câu cho một kết quả hạng (UI-0038-gold-definition): hạng tính trước khi cắt top-K
export function outcomeText(outcome: Outcome, k: number): string {
  switch (outcome.kind) {
    case "rank": {
      const rank = `rank ${rankText(outcome.from, outcome.to)}${outcome.from < outcome.to ? " (tied)" : ""}`;
      return outcome.from <= k ? `${rank}, inside the top ${k}` : `${rank} (outside top ${k})`;
    }
    case "not-found":
      return "not found: BM25 gives it a score of 0, because it shares no word with the question";
    case "filtered":
      return `filtered out at: ${FILTER_SHOWN[outcome.step]}`;
    case "in-progress":
      return "in progress";
  }
}

// Emoji riêng của Threads: API trả về thành ký tự ▓ (U+2593) trong chữ bài — Thy đối chiếu ứng dụng Threads trên
// 1 bài 2026-11-12. Thy chọn: chỉ lúc hiển thị thay bằng nhãn "[emoji]" (dữ liệu, điểm số không đổi; BM25 vốn bỏ qua
// ký tự này vì không phải chữ / số). Bản dịch Haiku chép lại ký tự nên cũng thay. Ký tự dính chữ sau (35 / 428 đoạn,
// đo 2026-11-25) → chèn 1 dấu cách, không thì "[emoji]But" đọc như một từ.
export const THREADS_EMOJI = "▓";
// Cờ = cặp "regional indicator" (U+1F1E6–U+1F1FF). Windows không có hình cờ nên hiện 2 chữ cái ("CP"). Trong 19 bài
// chỉ có 🇨🇵 và 🇫🇷 (đo 2026-11-25) — cả hai dùng làm cờ Pháp; cặp khác → "[flag]"
const FLAG = /[\u{1F1E6}-\u{1F1FF}]{2}/gu;
const FRENCH_FLAGS = new Set(["🇨🇵", "🇫🇷"]);
export function showEmoji(text: string): string {
  return text
    .replace(/▓(?=[^\s▓])/g, "[emoji] ")
    .replaceAll(THREADS_EMOJI, "[emoji]")
    .replace(FLAG, (flag) => (FRENCH_FLAGS.has(flag) ? "[French flag]" : "[flag]"));
}

// Bản TypeScript của `non_gold_kept` (`src/rag_demo/demo_file.py:483#non_gold_kept`): cặp (câu hỏi, đoạn) Haiku
// giữ (điểm ≥ mức giữ) mà đoạn không trúng đáp án ở cách chia nào, cộng qua các câu hỏi (ADR-0040: trang công bố
// số này). `top` = số cặp trong đó ở điểm tối đa. Mẫu số `pairs` = số cặp NGOÀI đáp án (copy-reviewer 2026-11-12:
// mẫu số cũ là mọi cặp, tính cả cặp đáp án); `allPairs` = số câu hỏi × số đoạn khác nhau của cả 7 cách chia.
export function nonGoldKept(
  demo: DemoFile,
  maxScore: number,
): { total: number; top: number; pairs: number; allPairs: number } {
  let total = 0;
  let top = 0;
  let pairs = 0;
  for (const question of demo.questions) {
    const gold = goldPassages(demo, question);
    question.llm.forEach((cell, passage) => {
      if (gold.has(passage)) return;
      pairs += 1;
      if (cell.score >= demo.provenance.llm_keep_min_score) {
        total += 1;
        if (cell.score === maxScore) top += 1;
      }
    });
  }
  return { total, top, pairs, allPairs: demo.questions.length * demo.passages.length };
}

// Đoạn (theo số thứ tự trong `passages`) trúng đáp án của câu hỏi ở ít nhất một cách chia
function goldPassages(demo: DemoFile, question: Question): Set<number> {
  const gold = new Set<number>();
  for (const way of Object.keys(question.gold_chunks) as Way[]) {
    const chunks = demo.ways[way];
    for (const ids of Object.values(question.gold_chunks[way])) {
      for (const id of ids) gold.add(chunks[id].passage);
    }
  }
  return gold;
}

// 2 ví dụ thật cho số "Extra partly answers" (UI-0040-honest-data-notes, reviewer 2026-11-12): Claude đọc đủ 43 cặp
// 2026-11-25 rồi chọn, Thy duyệt chữ. Số thứ tự đoạn đổi khi file demo dựng lại (bài bị xoá, đổi cách chia —
// code-reviewer 2026-11-25), nên mỗi ví dụ còn khoá bằng mã bài + một mẩu chữ gốc riêng của đoạn (đo 2026-11-25:
// "Gant, Tommy" chỉ có ở các đoạn của bài 18153699859548704, "cây bút" ở bài 18645332647003724).
// `honestExamples` bỏ ví dụ không còn khớp khoá, hoặc không còn là cặp ngoài đáp án được Haiku giữ.
export const HONEST_EXAMPLES = [
  {
    question: 2,
    passage: 55,
    unit: "18153699859548704",
    anchor: "Gant, Tommy",
    kind: "Partly answers",
    // copy-reviewer 2026-11-25: đoạn văn không nói "cheap" → bỏ
    why: "the stalls sell branded clothes as clearance stock (déstockage), not second-hand.",
  },
  {
    question: 7,
    passage: 52,
    unit: "18645332647003724",
    anchor: "cây bút",
    kind: "Haiku mistake",
    why: "the passage recommends a pen sold on Amazon and says nothing about food.",
  },
] as const;

export function honestExamples(demo: DemoFile): (typeof HONEST_EXAMPLES)[number][] {
  return HONEST_EXAMPLES.filter((example) => {
    const question = demo.questions.find((q) => q.number === example.question);
    const passage = demo.passages[example.passage];
    const cell = question?.llm[example.passage];
    return (
      question !== undefined &&
      passage !== undefined &&
      passage.unit === example.unit &&
      passage.text.includes(example.anchor) &&
      cell !== undefined &&
      cell.score >= demo.provenance.llm_keep_min_score &&
      !goldPassages(demo, question).has(example.passage)
    );
  });
}

// Chữ đếm ví dụ lấy từ số ví dụ còn hiện (reviewer 2026-11-25: "Two" viết cứng cạnh danh sách đã lọc). Tên giống
// ô số "Extra “partly answers”" ngay trên (copy-reviewer 2026-11-25)
const COUNT_WORDS = ["No", "One", "Two"];
export function examplesHeading(shown: number, extra: number): string {
  return `${COUNT_WORDS[shown] ?? String(shown)} of the ${extra.toLocaleString("en-US")} extra “partly answers”`;
}
export function examplesPointer(shown: number): string {
  return shown === 0 ? "" : shown === 1 ? " (a real example below)" : " (real examples below)";
}

// Câu trả lời của khối "Where the answer lands" — một câu đúng ngữ pháp cho từng loại kết quả (reviewer 2026-11-12:
// nhánh `not-found` từng ra "The correct answer is at not found: …")
export function answerSentence(question: Question, gold: { main: Outcome } | null, k: number): string {
  if (gold === null) {
    return `No content unit answers Q${question.number}, so there is no correct passage to rank. The list shows what retrieval returns anyway: the top passage is only the closest match.`;
  }
  const lead = question.rule === "both" ? "The answer needs 2 content units; the later one to appear" : "The correct answer";
  const outcome = gold.main;
  switch (outcome.kind) {
    case "rank":
      return `${lead} is at ${outcomeText(outcome, k)}.`;
    case "not-found":
      return `${lead} is not found: BM25 gives it a score of 0, because it shares no word with the question.`;
    case "filtered":
      return `${lead} was removed by the ${FILTER_SHOWN[outcome.step]}.`;
    case "in-progress":
      return `${lead} cannot be ranked yet: this setup is in progress.`;
  }
}

// Ghi chú của số "Correct answer rank" theo định nghĩa của từng câu (UI-0038-gold-definition): câu 3 / 7 = hạng của
// bài tìm thấy sau cùng; câu có vị trí đáp án (5, 8) chỉ tính đoạn chạm phần chứa ý
export function goldRankNote(question: Question, k: number): string {
  if (question.rule === "none") return "This question has no answer in the content units.";
  if (question.rule === "both") {
    return `The answer needs 2 content units: this is the rank of the one found later (each counted at its best-ranked passage), before the top-${k} cut.`;
  }
  if (Object.keys(question.gold_spans).length > 0) {
    return `Rank of the best-ranked passage that contains part of the answering text, before the top-${k} cut.`;
  }
  return `Rank of the best-ranked passage from the answering content unit, before the top-${k} cut.`;
}

export function goldUnitsSentence(question: Question): string {
  if (question.rule === "none") return "No content unit answers it.";
  if (question.rule === "both") return "The answer needs both of 2 content units.";
  return question.gold_unit_ids.length > 1
    ? `Either of ${question.gold_unit_ids.length} content units answers it.`
    : "One content unit answers it.";
}
