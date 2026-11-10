// Bộ đọc file demo RAG định dạng 2 (`build_demo` của `src/rag_demo/demo_file.py`, ADR-0041).
// Kiểm cấu trúc và kiểu của mọi trường bước tìm dùng, để file lạ không làm engine ra số sai hay crash.
import { SCORE_DECIMALS } from "./rank.ts";

// Bản Python: `src/rag_demo/demo_file.py:59#DEMO_FILE_FORMAT`.
export const DEMO_FILE_FORMAT = 2;

// Thứ tự cách chia như file và bảng đo của ADR-0041.
export const WAYS = [
  "whole",
  "post",
  "fixed_300",
  "fixed_500",
  "fixed_800",
  "recursive_500",
  "semantic",
] as const;
export type Way = (typeof WAYS)[number];

export type Topic = { id: string | null; label_en: string }; // id null = "Unclustered"
export type Post = { id: string; start: number; end: number }; // UTF-16, nửa mở
export type Unit = {
  id: string;
  text: string;
  sha256: string;
  month: string; // "YYYY-MM", giờ Paris của post mở đầu
  topic: Topic;
  posts: Post[];
};
export type Passage = {
  unit: string;
  text: string;
  en: string;
  context: string | null; // null ở cách "whole": chunk đã là cả bài (ADR-0039 D2)
  context_en: string | null;
};
export type WayChunk = { id: number; unit: string; start: number; end: number; passage: number };
export type LlmCell = {
  score: number; // Haiku 0–3
  quote: string | null;
  quote_en: string | null;
  quote_dropped: string | null;
};
export type Transforms = {
  rewrite: string;
  rewrite_en: string;
  expand: string;
  expand_en: string;
  hyde: string;
  hyde_en: string;
  multi_query: string[];
  multi_query_en: string[];
  decompose: string[];
  decompose_en: string[];
  step_back: string;
  step_back_en: string;
};
export type Question = {
  number: number;
  text: string;
  english: string;
  rule: "single" | "both" | "none";
  gold_unit_ids: string[];
  gold_spans: Record<string, { start: number; end: number }>;
  gold_chunks: Record<Way, Record<string, number[]>>; // mã chunk trúng theo bài
  transforms: Transforms;
  dense: number[]; // theo passage
  cross_encoder: number[]; // theo passage, logit thô
  llm: LlmCell[]; // theo passage
};
export type Provenance = {
  score_decimals: number;
  pending: string[];
  llm_keep_min_score: number;
  // cả hai null khi DB chưa có lần gom cụm nào (mọi bài Unclustered)
  topics: { cluster_run_id: number | null; cluster_run_at: string | null };
  [key: string]: unknown;
};
export type DemoFile = {
  format: number;
  provenance: Provenance;
  units: Unit[];
  passages: Passage[];
  ways: Record<Way, WayChunk[]>;
  cosine: Record<Way, number[]>; // tam giác trên theo hàng, thứ tự mã chunk
  questions: Question[];
};

export class DemoFileError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DemoFileError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireArray(value: unknown, what: string): unknown[] {
  if (!Array.isArray(value)) throw new DemoFileError(`${what} must be a list`);
  return value;
}

// Từ chối file engine không đọc đúng được: định dạng khác, số chữ số làm tròn khác hằng của engine
// (luật hoà dựa vào nó, ADR-0041 Hệ quả), mã chunk khác vị trí (phá hoà theo mã chunk), passage ngoài
// danh sách, mảng điểm theo passage lệch độ dài, ma trận cosine lệch số chunk.
export function parseDemoFile(raw: unknown): DemoFile {
  if (!isRecord(raw)) throw new DemoFileError("demo file must be a JSON object");
  if (raw.format !== DEMO_FILE_FORMAT) {
    throw new DemoFileError(
      `demo file format ${String(raw.format)} is not supported (expected ${DEMO_FILE_FORMAT})`,
    );
  }
  const provenance = raw.provenance;
  if (!isRecord(provenance) || provenance.score_decimals !== SCORE_DECIMALS) {
    const found = isRecord(provenance) ? String(provenance.score_decimals) : "missing";
    throw new DemoFileError(
      `score_decimals ${found} does not match the engine (${SCORE_DECIMALS})`,
    );
  }
  if (!sameStrings(provenance.pending, PENDING_PARTS)) {
    throw new DemoFileError("provenance.pending differs from the pending parts this engine assumes");
  }
  const passages = requireArray(raw.passages, "passages");
  passages.forEach(checkPassage);
  const passageCount = passages.length;
  if (!isRecord(raw.ways) || !isRecord(raw.cosine)) {
    throw new DemoFileError("ways and cosine must be objects keyed by chunking way");
  }
  for (const way of WAYS) {
    const chunks = requireArray(raw.ways[way], `ways.${way}`);
    chunks.forEach((chunk, position) => {
      if (!isRecord(chunk) || chunk.id !== position) {
        throw new DemoFileError(`ways.${way}[${position}] must have id ${position}`);
      }
      const passage = chunk.passage;
      if (!Number.isInteger(passage) || (passage as number) < 0 || (passage as number) >= passageCount) {
        throw new DemoFileError(`ways.${way}[${position}] points to a missing passage`);
      }
    });
    const pairs = (chunks.length * (chunks.length - 1)) / 2;
    if (requireArray(raw.cosine[way], `cosine.${way}`).length !== pairs) {
      throw new DemoFileError(`cosine.${way} must hold ${pairs} values`);
    }
  }
  requireArray(raw.questions, "questions").forEach((question, i) => {
    if (!isRecord(question)) throw new DemoFileError(`questions[${i}] must be an object`);
    checkQuestionText(question, i);
    const dense = question.dense;
    if (!Array.isArray(dense) || !dense.every((value) => Number.isFinite(value))) {
      throw new DemoFileError(`questions[${i}].dense must hold finite numbers`);
    }
    for (const key of ["dense", "cross_encoder", "llm"]) {
      if (requireArray(question[key], `questions[${i}].${key}`).length !== passageCount) {
        throw new DemoFileError(`questions[${i}].${key} must hold one value per passage`);
      }
    }
  });
  return raw as unknown as DemoFile;
}

// Bản Python: `src/rag_demo/demo_file.py:76#PENDING_PARTS`. Engine viết cứng các trạng thái "hybrid rơi
// về BM25" / "dense trần cần phần còn chờ" theo đúng 2 mục này (ADR-0041 Luật chung 8): file khác danh
// sách thì engine phải sửa theo, không đọc tiếp với giả định cũ.
export const PENDING_PARTS = [
  "dense score of transformed questions",
  "dense score of chunks with their context sentence",
] as const;

function sameStrings(value: unknown, expected: readonly string[]): boolean {
  return (
    Array.isArray(value) &&
    value.length === expected.length &&
    value.every((item, i) => item === expected[i])
  );
}

function isStringList(value: unknown): boolean {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function checkPassage(passage: unknown, i: number): void {
  if (
    !isRecord(passage) ||
    typeof passage.text !== "string" ||
    !(typeof passage.context === "string" || passage.context === null)
  ) {
    throw new DemoFileError(`passages[${i}] needs text (string) and context (string or null)`);
  }
}

// Câu con của mọi cách biến đổi (Luật chung 4): chuỗi đơn, hoặc danh sách chuỗi ở multi-query / decompose.
function checkQuestionText(question: Record<string, unknown>, i: number): void {
  const t = question.transforms;
  const singles = ["rewrite", "expand", "hyde", "step_back"];
  if (
    typeof question.text !== "string" ||
    !isRecord(t) ||
    !singles.every((key) => typeof t[key] === "string") ||
    !isStringList(t.multi_query) ||
    !isStringList(t.decompose)
  ) {
    throw new DemoFileError(`questions[${i}] needs text and transforms as strings / string lists`);
  }
}
