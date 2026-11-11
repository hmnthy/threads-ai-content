// Ba bước lọc của demo RAG (ADR-0041, bảng từng bước): lọc metadata trước bước tìm; lọc Haiku và lọc
// gần trùng sau rerank. Bước lọc chỉ bỏ bớt đoạn rồi đánh lại hạng theo vị trí (Luật chung 6).
import type { DemoFile, Question, Way } from "./demoFile.ts";
import { RERANK_KEEP_MIN_SCORE } from "./demoFile.ts";
import { position, renumber } from "./rank.ts";
import type { Row } from "./rank.ts";

// "Phần của thread": post mở đầu hay các post viết tiếp.
export type ThreadPart = "opening" | "continuation";
// Mỗi trường chọn nhiều giá trị; mảng rỗng = không lọc trường đó. Topic theo `topic.id`, null =
// "Unclustered" (một giá trị như mọi topic).
export type MetadataSelection = {
  topics: (string | null)[];
  months: string[];
  parts: ThreadPart[];
};
export const NO_METADATA_FILTER: MetadataSelection = { topics: [], months: [], parts: [] };

// Chunk "chạm" phần nào thì khớp phần đó: giao khác rỗng giữa hai khoảng nửa mở [start, end); chunk vắt
// qua khớp cả hai (Thy chọn, ADR-0041).
export function chunkParts(demo: DemoFile, way: Way, chunk: number): ThreadPart[] {
  const record = demo.ways[way][chunk];
  const unit = demo.units.find((u) => u.id === record.unit);
  if (unit === undefined) throw new Error(`chunk ${chunk} points to a missing unit`);
  const parts: ThreadPart[] = [];
  unit.posts.forEach((post, i) => {
    const touches = record.start < post.end && post.start < record.end;
    const part: ThreadPart = i === 0 ? "opening" : "continuation";
    if (touches && !parts.includes(part)) parts.push(part);
  });
  return parts;
}

// Số chunk vắt qua cả hai phần ở cách chia này (trang ghi ra cạnh bộ lọc).
export function straddlingChunks(demo: DemoFile, way: Way): number {
  return demo.ways[way].filter((c) => chunkParts(demo, way, c.id).length > 1).length;
}

// OR trong một trường, AND giữa các trường (quy ước tìm kiếm theo mặt — faceted search). Trả mã chunk
// còn lại, tăng dần.
export function metadataCandidates(
  demo: DemoFile,
  way: Way,
  selection: MetadataSelection,
): number[] {
  const units = new Map(demo.units.map((unit) => [unit.id, unit]));
  return demo.ways[way]
    .filter((chunk) => {
      const unit = units.get(chunk.unit);
      if (unit === undefined) throw new Error(`chunk ${chunk.id} points to a missing unit`);
      const topicOk = selection.topics.length === 0 || selection.topics.includes(unit.topic.id);
      const monthOk = selection.months.length === 0 || selection.months.includes(unit.month);
      const partOk =
        selection.parts.length === 0 ||
        chunkParts(demo, way, chunk.id).some((part) => selection.parts.includes(part));
      return topicOk && monthOk && partOk;
    })
    .map((chunk) => chunk.id);
}

export type FilterResult = { rows: Row[]; dropped: number[] }; // dropped = mã chunk bị bỏ, theo thứ tự

// Điểm Haiku của chunk (chấm theo câu hỏi gốc, Luật chung 7), đọc qua passage của chunk.
export function haikuScore(demo: DemoFile, question: Question, way: Way, chunk: number): number {
  return question.llm[demo.ways[way][chunk].passage].score;
}

export function haikuKeeps(score: number): boolean {
  return score >= RERANK_KEEP_MIN_SCORE;
}

// Lọc Haiku: bỏ đoạn < 2, trên cả danh sách kể cả đuôi "not reranked"; bật được với mọi lựa chọn rerank.
export function haikuFilter(
  demo: DemoFile,
  question: Question,
  way: Way,
  rows: readonly Row[],
): FilterResult {
  const keep = rows.filter((row) => haikuKeeps(haikuScore(demo, question, way, row.chunk)));
  return finish(rows, keep);
}

// Cosine chunk × chunk của chữ gốc (Luật chung 8), tam giác trên theo hàng, thứ tự mã chunk.
export function cosineOf(demo: DemoFile, way: Way, a: number, b: number): number {
  if (a === b) throw new Error("cosine of a chunk with itself is not stored");
  const n = demo.ways[way].length;
  const i = Math.min(a, b);
  const j = Math.max(a, b);
  return demo.cosine[way][i * n - (i * (i + 1)) / 2 + (j - i - 1)];
}

// Ngưỡng gần trùng: thanh kéo 0,50–1,00 bước 0,01 (vị trí 50–100), mặc định 0,95.
export const NEAR_DUPLICATE_DEFAULT = 95;

// Đi theo thứ tự, bỏ đoạn có cosine ≥ ngưỡng với một đoạn ĐÃ GIỮ đứng trước (đoạn bị bỏ không loại
// thêm ai).
export function nearDuplicateFilter(
  demo: DemoFile,
  way: Way,
  rows: readonly Row[],
  thresholdHundredths: number,
): FilterResult {
  const threshold = position(thresholdHundredths, 50, 100) / 100;
  const keep: Row[] = [];
  for (const row of rows) {
    if (!keep.some((kept) => cosineOf(demo, way, kept.chunk, row.chunk) >= threshold)) keep.push(row);
  }
  return finish(rows, keep);
}

function finish(rows: readonly Row[], keep: readonly Row[]): FilterResult {
  const kept = new Set(keep.map((row) => row.chunk));
  return {
    rows: renumber(keep),
    dropped: rows.filter((row) => !kept.has(row.chunk)).map((row) => row.chunk),
  };
}
