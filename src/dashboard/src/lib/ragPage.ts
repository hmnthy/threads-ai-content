// Chữ và hàm phụ của trang /rag-pipeline bản đầu (Thy chốt 2026-11-12: 3 khối + khối Loading và bản đồ pipeline thêm sau, chỉ component có sẵn — phạm vi ở
// `docs/design/ui-contract-audit.md`, mục "`/rag-pipeline` — trang bản đầu thu hẹp"). Chữ hiển thị là bản nháp,
// copy-reviewer đọc rồi Thy duyệt. File thường (không "use client") để server component import được.
import type { DemoFile, Question, Way } from "./ragDemo/demoFile.ts";
import type { Outcome } from "./ragDemo/answer.ts";
import type { Rerank } from "./ragDemo/rerank.ts";
import type { Retriever } from "./ragDemo/retrieve.ts";

// Một nguồn cho dải mục lục đầu trang và nhãn trên tiêu đề mỗi khối (như `topicSections.ts`)
// Thy 2026-11-12 (phương án A): thêm khối Loading đứng đầu — bước đầu của pipeline trong repo mẫu (Loader)
// Thy 2026-11-12: thêm bản đồ pipeline đứng đầu — đối chiếu từng bước với chuẩn repo mẫu của thầy Thy
export const RAG_SECTIONS = [
  ["pipeline", "01", "Pipeline map"],
  ["loading", "02", "Loading"],
  ["question", "03", "Question"],
  ["passages", "04", "Ranked passages"],
  ["about", "05", "About this demo"],
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
    block: "passages",
    what: "Cuts each content unit into passages, with 7 methods to choose from. Adding a context sentence to each passage comes in a later version.",
  },
  {
    number: 3,
    name: "Embedding",
    stage: "indexing",
    optional: false,
    status: "fixed",
    block: "passages",
    what: "Dense: OpenAI text-embedding-3-small vectors, made before publishing. Sparse: BM25 needs no vectors; its word counts are rebuilt in your browser for the chunking you pick. A view of how similar the passages are to each other (cosine similarity, already in the file) comes in a later version.",
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
    what: "Rewriting the question before searching (rewrite, expand, HyDE, multi-query, decompose, step-back). The rewrites are stored and BM25 can already search with them, but their dense scores are not computed yet, so this version searches with the original question.",
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

export function ragShort(id: (typeof RAG_SECTIONS)[number][0]): string {
  return RAG_SECTIONS.find(([key]) => key === id)![2];
}

// Hiện tượng mỗi câu hỏi phô ra — bảng D10 của ADR-0037 (Thy duyệt 2026-11-05), dịch sang tiếng Anh
export const QUESTION_TESTS: Record<number, string> = {
  1: "typed without Vietnamese diacritics",
  2: "the answer uses other words, partly in another language",
  3: "one question with several parts; the answer needs 2 content units",
  // ADR-0040: bài gần trùng thứ hai bị xoá trên Threads sau mốc đóng băng → còn 1 bài đáp án
  4: "near-duplicate posts; the second one was deleted from Threads after the freeze, so one content unit answers it",
  5: "the answer sits in a follow-up post of the thread",
  6: "asked in French about a post written in Vietnamese",
  7: "vague; the answer needs 2 content units",
  8: "a keyword trap: another post also talks about prices",
  9: "numbers and product names",
  10: "no content unit answers it",
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
  semantic: {
    label: "Semantic",
    sentence:
      "Cut between two sentences when their meanings are among the least similar quarter of all neighbouring pairs, at most 800 characters.",
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
      return `filtered out at: ${outcome.step}`;
    case "in-progress":
      return "in progress";
  }
}

// Emoji riêng của Threads: API trả về thành ký tự ▓ (U+2593) trong chữ bài — Thy đối chiếu ứng dụng Threads trên
// 1 bài 2026-11-12. Thy chọn: chỉ lúc hiển thị thay bằng nhãn "[emoji]" (dữ liệu, điểm số không đổi; BM25 vốn bỏ qua
// ký tự này vì không phải chữ / số). Bản dịch Haiku chép lại ký tự nên cũng thay.
export const THREADS_EMOJI = "▓";
export function showEmoji(text: string): string {
  return text.replaceAll(THREADS_EMOJI, "[emoji]");
}

// Bản TypeScript của `non_gold_kept` (`src/rag_demo/demo_file.py:483#non_gold_kept`): cặp (câu hỏi, đoạn) Haiku
// giữ (điểm ≥ mức giữ) mà đoạn không trúng đáp án ở cách chia nào, cộng qua các câu hỏi (ADR-0040: trang công bố
// số này). `pairs` = mẫu số: số câu hỏi × số đoạn khác nhau của cả 7 cách chia; `top` = số cặp trong đó ở điểm tối đa.
export function nonGoldKept(demo: DemoFile, maxScore: number): { total: number; top: number; pairs: number } {
  let total = 0;
  let top = 0;
  for (const question of demo.questions) {
    const gold = new Set<number>();
    for (const way of Object.keys(question.gold_chunks) as Way[]) {
      const chunks = demo.ways[way];
      for (const ids of Object.values(question.gold_chunks[way])) {
        for (const id of ids) gold.add(chunks[id].passage);
      }
    }
    question.llm.forEach((cell, passage) => {
      if (cell.score >= demo.provenance.llm_keep_min_score && !gold.has(passage)) {
        total += 1;
        if (cell.score === maxScore) top += 1;
      }
    });
  }
  return { total, top, pairs: demo.questions.length * demo.passages.length };
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
