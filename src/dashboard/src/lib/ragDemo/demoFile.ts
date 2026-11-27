// Bộ đọc file demo RAG định dạng 2 và 3 (`build_demo` của `src/rag_demo/demo_file.py`, ADR-0041).
// Kiểm cấu trúc và kiểu của mọi trường engine dùng, để file lạ không làm engine ra số sai hay crash.
import { SCORE_DECIMALS } from "./rank.ts";

// Bản Python: `src/rag_demo/demo_file.py:62#DEMO_FILE_FORMAT` — định dạng `assemble` ghi hiện nay.
export const DEMO_FILE_FORMAT = 3;

// 2 phần còn chờ (`provenance.pending`). Engine quyết "hybrid rơi về BM25" / "dense trần cần phần còn
// chờ" (ADR-0041 Luật chung 8) theo mục `pending` của CHÍNH file đang đọc (`retrievalPlan`).
export const PENDING_TRANSFORMED = "dense score of transformed questions";
export const PENDING_CONTEXT = "dense score of chunks with their context sentence";
// Định dạng 3 tính đủ cả hai (RAG PR 3a); bản Python: `src/rag_demo/demo_file.py:81#PENDING_PARTS`.
export const PENDING_PARTS = [] as const;
// Định dạng 2 ghi đúng 2 mục này. Trang vẫn đọc định dạng 2 (bản trên Blob tới lần publish kế tiếp):
// file khác danh sách thì engine phải sửa theo, không đọc tiếp với giả định cũ.
export const FORMAT_2_PENDING_PARTS = [PENDING_TRANSFORMED, PENDING_CONTEXT] as const;
const PENDING_BY_FORMAT: Record<number, readonly string[]> = {
  2: FORMAT_2_PENDING_PARTS,
  3: PENDING_PARTS,
};

// Mức "giữ" của Haiku (thang 0–3): nhãn keep / drop ở rerank Haiku, ngưỡng của lọc Haiku. Lựa chọn
// thiết kế, bản Python `src/rag_demo/llm_jobs.py:46#RERANK_KEEP_MIN_SCORE`; file ghi số khác bị từ chối.
export const RERANK_KEEP_MIN_SCORE = 2;
export const LLM_MAX_SCORE = 3;

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
// Định dạng 3: điểm dense của một câu con biến đổi với chữ đoạn trần và với chuỗi kèm câu ngữ cảnh
// (câu ngữ cảnh, xuống dòng, đoạn — như BM25), theo passage
export type SubQueryDense = { plain: number[]; context: number[] };
export type TransformDense = {
  rewrite: SubQueryDense;
  expand: SubQueryDense;
  hyde: SubQueryDense;
  step_back: SubQueryDense;
  multi_query: SubQueryDense[]; // cùng thứ tự `transforms.multi_query`
  decompose: SubQueryDense[];
};
export type Rule = "single" | "both" | "none";
export type Question = {
  number: number;
  text: string;
  english: string;
  rule: Rule;
  gold_unit_ids: string[];
  gold_spans: Record<string, { start: number; end: number }>;
  gold_chunks: Record<Way, Record<string, number[]>>; // mã chunk trúng theo bài
  transforms: Transforms;
  dense: number[]; // theo passage
  // định dạng 3 (không có ở định dạng 2 — khi đó `provenance.pending` ghi 2 mục còn chờ)
  dense_context?: number[]; // câu gốc với đoạn kèm câu ngữ cảnh, theo passage
  transform_dense?: TransformDense;
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
// (luật hoà dựa vào nó, ADR-0041 Hệ quả), mức giữ Haiku khác, mã chunk khác vị trí (phá hoà theo mã
// chunk), chunk trỏ ra ngoài bài / passage, mảng điểm theo passage lệch độ dài hay sai kiểu, ma trận
// cosine lệch số chunk, chunk đáp án không thuộc bài của nó.
export function parseDemoFile(raw: unknown): DemoFile {
  if (!isRecord(raw)) throw new DemoFileError("demo file must be a JSON object");
  if (typeof raw.format !== "number" || !Object.hasOwn(PENDING_BY_FORMAT, raw.format)) {
    throw new DemoFileError(
      `demo file format ${String(raw.format)} is not supported (expected 2 or ${DEMO_FILE_FORMAT})`,
    );
  }
  const format = raw.format;
  checkProvenance(raw.provenance, PENDING_BY_FORMAT[format]);
  const units = new Map<string, number>();
  requireArray(raw.units, "units").forEach((unit, i) => {
    const id = checkUnit(unit, i);
    // mã trùng: bộ lọc metadata và "phần của thread" sẽ đọc hai bản khác nhau của cùng một bài
    if (units.has(id)) throw new DemoFileError(`units[${i}] repeats unit id ${id}`);
    units.set(id, (unit as { text: string }).text.length);
  });
  const passages = requireArray(raw.passages, "passages");
  passages.forEach((passage, i) => checkPassage(passage, i, units));
  const passageCount = passages.length;
  if (!isRecord(raw.ways) || !isRecord(raw.cosine)) {
    throw new DemoFileError("ways and cosine must be objects keyed by chunking way");
  }
  const chunkUnits = new Map<Way, string[]>();
  for (const way of WAYS) {
    const chunks = requireArray(raw.ways[way], `ways.${way}`);
    chunkUnits.set(
      way,
      chunks.map((chunk, position) => checkChunk(chunk, `ways.${way}[${position}]`, position, {
        units,
        passages: passages as Passage[],
      })),
    );
    const pairs = (chunks.length * (chunks.length - 1)) / 2;
    const cosine = requireArray(raw.cosine[way], `cosine.${way}`);
    if (cosine.length !== pairs) throw new DemoFileError(`cosine.${way} must hold ${pairs} values`);
    if (!cosine.every((v) => Number.isFinite(v) && (v as number) >= -1 && (v as number) <= 1)) {
      throw new DemoFileError(`cosine.${way} must hold numbers in [-1, 1]`);
    }
  }
  requireArray(raw.questions, "questions").forEach((question, i) => {
    if (!isRecord(question)) throw new DemoFileError(`questions[${i}] must be an object`);
    checkQuestionText(question, i);
    checkScores(question, i, passageCount);
    if (format === 3) checkFormat3Scores(question, i, passageCount);
    checkGold(question, i, chunkUnits);
  });
  return raw as unknown as DemoFile;
}

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

// Danh sách câu con rỗng không phải câu hỏi không khớp: là file hỏng, phải dừng lúc đọc thay vì để
// trang ghi "no passages left after: merge" (Luật chung 6).
function isSubQueryList(value: unknown): boolean {
  return isStringList(value) && (value as string[]).length > 0;
}

function isOffset(value: unknown): value is number {
  return Number.isInteger(value) && (value as number) >= 0;
}

function checkProvenance(provenance: unknown, pending: readonly string[]): void {
  if (!isRecord(provenance) || provenance.score_decimals !== SCORE_DECIMALS) {
    const found = isRecord(provenance) ? String(provenance.score_decimals) : "missing";
    throw new DemoFileError(
      `score_decimals ${found} does not match the engine (${SCORE_DECIMALS})`,
    );
  }
  if (!sameStrings(provenance.pending, pending)) {
    throw new DemoFileError("provenance.pending differs from the pending parts this engine assumes");
  }
  if (provenance.llm_keep_min_score !== RERANK_KEEP_MIN_SCORE) {
    throw new DemoFileError(
      `llm_keep_min_score ${String(provenance.llm_keep_min_score)} does not match the engine (${RERANK_KEEP_MIN_SCORE})`,
    );
  }
}

// Bài: mã duy nhất, tháng "YYYY-MM", topic (mã chuỗi hoặc null = Unclustered), các post có khoảng
// nửa mở tăng dần, không chồng nhau, nằm trong chữ của bài (lọc "phần của thread" dựa vào chúng).
function checkUnit(unit: unknown, i: number): string {
  const where = `units[${i}]`;
  if (
    !isRecord(unit) ||
    typeof unit.id !== "string" ||
    typeof unit.text !== "string" ||
    typeof unit.month !== "string" ||
    !/^\d{4}-(0[1-9]|1[0-2])$/.test(unit.month)
  ) {
    throw new DemoFileError(`${where} needs id, text and month (YYYY-MM)`);
  }
  const topic = unit.topic;
  if (
    !isRecord(topic) ||
    !(typeof topic.id === "string" || topic.id === null) ||
    typeof topic.label_en !== "string"
  ) {
    throw new DemoFileError(`${where}.topic needs id (string or null) and label_en`);
  }
  const posts = requireArray(unit.posts, `${where}.posts`);
  let previousEnd = 0;
  posts.forEach((post, j) => {
    if (
      !isRecord(post) ||
      !isOffset(post.start) ||
      !isOffset(post.end) ||
      post.start < previousEnd ||
      post.end <= post.start ||
      post.end > (unit.text as string).length
    ) {
      throw new DemoFileError(`${where}.posts[${j}] must be an ordered span inside the unit text`);
    }
    previousEnd = post.end;
  });
  if (posts.length === 0) throw new DemoFileError(`${where}.posts must not be empty`);
  return unit.id;
}

function checkPassage(passage: unknown, i: number, units: ReadonlyMap<string, number>): void {
  if (
    !isRecord(passage) ||
    typeof passage.text !== "string" ||
    !(typeof passage.context === "string" || passage.context === null) ||
    typeof passage.unit !== "string" ||
    !units.has(passage.unit)
  ) {
    throw new DemoFileError(
      `passages[${i}] needs text (string), context (string or null) and a known unit`,
    );
  }
}

// Chunk: mã = vị trí, khoảng nửa mở trong chữ của bài, passage có thật và cùng bài.
function checkChunk(
  chunk: unknown,
  where: string,
  position: number,
  known: { units: ReadonlyMap<string, number>; passages: readonly Passage[] },
): string {
  if (!isRecord(chunk) || chunk.id !== position) {
    throw new DemoFileError(`${where} must have id ${position}`);
  }
  const passage = chunk.passage;
  if (!Number.isInteger(passage) || (passage as number) < 0 || (passage as number) >= known.passages.length) {
    throw new DemoFileError(`${where} points to a missing passage`);
  }
  const unitLength = typeof chunk.unit === "string" ? known.units.get(chunk.unit) : undefined;
  if (
    unitLength === undefined ||
    known.passages[passage as number].unit !== chunk.unit ||
    !isOffset(chunk.start) ||
    !isOffset(chunk.end) ||
    chunk.end <= chunk.start ||
    chunk.end > unitLength
  ) {
    throw new DemoFileError(`${where} needs a known unit, its passage's unit and a span inside it`);
  }
  return chunk.unit as string;
}

// Câu con của mọi cách biến đổi (Luật chung 4): chuỗi đơn, hoặc danh sách chuỗi ở multi-query / decompose.
function checkQuestionText(question: Record<string, unknown>, i: number): void {
  const t = question.transforms;
  const singles = ["rewrite", "expand", "hyde", "step_back"];
  if (
    typeof question.text !== "string" ||
    !isRecord(t) ||
    !singles.every((key) => typeof t[key] === "string") ||
    !isSubQueryList(t.multi_query) ||
    !isSubQueryList(t.decompose)
  ) {
    throw new DemoFileError(`questions[${i}] needs text and transforms as strings / string lists`);
  }
}

// Điểm theo passage: dense, cross-encoder là số hữu hạn; Haiku là số nguyên 0–3.
function checkScores(question: Record<string, unknown>, i: number, passageCount: number): void {
  for (const key of ["dense", "cross_encoder", "llm"]) {
    if (requireArray(question[key], `questions[${i}].${key}`).length !== passageCount) {
      throw new DemoFileError(`questions[${i}].${key} must hold one value per passage`);
    }
  }
  for (const key of ["dense", "cross_encoder"]) {
    if (!(question[key] as unknown[]).every((value) => Number.isFinite(value))) {
      throw new DemoFileError(`questions[${i}].${key} must hold finite numbers`);
    }
  }
  const llm = question.llm as unknown[];
  if (
    !llm.every(
      (cell) =>
        isRecord(cell) &&
        Number.isInteger(cell.score) &&
        (cell.score as number) >= 0 &&
        (cell.score as number) <= LLM_MAX_SCORE,
    )
  ) {
    throw new DemoFileError(`questions[${i}].llm scores must be integers 0–${LLM_MAX_SCORE}`);
  }
}

function isScoreRow(value: unknown, passageCount: number): boolean {
  return (
    Array.isArray(value) && value.length === passageCount && value.every((v) => Number.isFinite(v))
  );
}

function isSubQueryDense(value: unknown, passageCount: number): boolean {
  return (
    isRecord(value) &&
    isScoreRow(value.plain, passageCount) &&
    isScoreRow(value.context, passageCount)
  );
}

// Định dạng 3: `dense_context` một số mỗi passage; `transform_dense` cùng cấu trúc `transforms` (câu
// đơn → 1 cặp mảng; multi-query / decompose → đúng bằng số câu con), mỗi mảng một số mỗi passage.
// Lệch → dừng lúc đọc, không để dense của câu con này rơi vào câu con khác.
function checkFormat3Scores(question: Record<string, unknown>, i: number, passageCount: number): void {
  const where = `questions[${i}]`;
  if (!isScoreRow(question.dense_context, passageCount)) {
    throw new DemoFileError(`${where}.dense_context must hold one finite number per passage`);
  }
  const dense = question.transform_dense;
  const t = question.transforms as Record<string, unknown>;
  const singles = ["rewrite", "expand", "hyde", "step_back"];
  const lists = ["multi_query", "decompose"];
  if (
    !isRecord(dense) ||
    !singles.every((key) => isSubQueryDense(dense[key], passageCount)) ||
    !lists.every(
      (key) =>
        Array.isArray(dense[key]) &&
        (dense[key] as unknown[]).length === (t[key] as unknown[]).length &&
        (dense[key] as unknown[]).every((sub) => isSubQueryDense(sub, passageCount)),
    )
  ) {
    throw new DemoFileError(
      `${where}.transform_dense must give plain and context scores for every rewritten question`,
    );
  }
}

// Đáp án: số bài khớp luật (single 1, both 2, none 0); mỗi cách chia liệt kê đúng các bài đáp án, mỗi
// bài ít nhất một chunk trúng, chunk có thật và thuộc đúng bài đó (hạng của đáp án dựa vào chúng).
const RULE_UNITS: Record<Rule, number> = { single: 1, both: 2, none: 0 };

function checkGold(
  question: Record<string, unknown>,
  i: number,
  chunkUnits: ReadonlyMap<Way, readonly string[]>,
): void {
  const where = `questions[${i}]`;
  const rule = question.rule as Rule;
  const gold = question.gold_unit_ids;
  if (
    !Object.hasOwn(RULE_UNITS, rule as string) ||
    !isStringList(gold) ||
    new Set(gold as string[]).size !== (gold as string[]).length ||
    (gold as string[]).length !== RULE_UNITS[rule]
  ) {
    throw new DemoFileError(`${where} needs a rule and that many distinct gold units`);
  }
  const byWay = question.gold_chunks;
  if (!isRecord(byWay)) throw new DemoFileError(`${where}.gold_chunks must be an object`);
  for (const way of WAYS) {
    const hits = byWay[way];
    const owners = chunkUnits.get(way) as readonly string[];
    if (!isRecord(hits) || !sameStrings(Object.keys(hits).sort(), [...(gold as string[])].sort())) {
      throw new DemoFileError(`${where}.gold_chunks.${way} must list exactly the gold units`);
    }
    for (const [unit, chunks] of Object.entries(hits)) {
      if (
        !Array.isArray(chunks) ||
        chunks.length === 0 ||
        !chunks.every((c) => Number.isInteger(c) && owners[c as number] === unit)
      ) {
        throw new DemoFileError(`${where}.gold_chunks.${way}.${unit} must list chunks of that unit`);
      }
    }
  }
}
