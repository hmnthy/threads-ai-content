// Nối mọi bước của demo RAG theo thứ tự ADR-0041 Luật chung 1: lọc metadata → tìm → gộp câu con →
// trộn → rerank (top-N) → lọc Haiku → lọc gần trùng → MMR → cắt top-K để hiển thị.
import type { DemoFile, Question, Way } from "./demoFile.ts";
import {
  haikuFilter,
  metadataCandidates,
  NEAR_DUPLICATE_DEFAULT,
  NO_METADATA_FILTER,
  nearDuplicateFilter,
} from "./filters.ts";
import type { MetadataSelection } from "./filters.ts";
import { LAMBDA_DEFAULT, mmr } from "./mmr.ts";
import { overlaps, position, toRows } from "./rank.ts";
import type { Row } from "./rank.ts";
import {
  rerankCrossEncoder,
  rerankHaiku,
  splitReranked,
  TOP_N_DEFAULT,
  TOP_N_RANGE,
} from "./rerank.ts";
import type { Rerank } from "./rerank.ts";
import { DEFAULT_RETRIEVAL, retrieve } from "./retrieve.ts";
import type { Query, RetrievalConfig, RetrievalResult, RetrievalStep, WayIndex } from "./retrieve.ts";

export type PipelineConfig = RetrievalConfig & {
  metadata: MetadataSelection;
  rerank: Rerank;
  topN: number; // N của rerank, 5–50
  haikuFilter: boolean;
  nearDuplicate: boolean;
  nearDuplicateThreshold: number; // vị trí thanh kéo 50–100
  mmr: boolean;
  lambda: number; // vị trí thanh kéo 0–100
  topK: number; // 1–20
};

// Thanh kéo K: 1–20, mặc định 10 (lựa chọn thiết kế).
export const TOP_K_DEFAULT = 10;
export const TOP_K_RANGE = [1, 20] as const;

// Mặc định khi mở trang (ADR-0041, lựa chọn thiết kế): hybrid RRF, chưa rerank, mọi bước lọc và MMR tắt.
export const DEFAULT_PIPELINE: PipelineConfig = {
  ...DEFAULT_RETRIEVAL,
  metadata: NO_METADATA_FILTER,
  rerank: "none",
  topN: TOP_N_DEFAULT,
  haikuFilter: false,
  nearDuplicate: false,
  nearDuplicateThreshold: NEAR_DUPLICATE_DEFAULT,
  mmr: false,
  lambda: LAMBDA_DEFAULT,
  topK: TOP_K_DEFAULT,
};

// Bước đầu tiên làm rỗng danh sách (Luật chung 6). Rerank và MMR không bỏ đoạn nên không có mã.
export type StepCode = RetrievalStep | "haiku-filter" | "near-duplicate";
// Thứ tự bước để chọn "bước đứng sau" (mục "Hạng của đáp án").
export const REMOVING_STEPS = ["metadata", "bm25", "haiku-filter", "near-duplicate"] as const;
export type RemovingStep = (typeof REMOVING_STEPS)[number];

export type ReorderStep = { input: Row[]; output: Row[] }; // rerank, MMR: mũi tên so input với output
export type FilterStep = { rows: Row[]; dropped: number[] };
export type TopKCut = { k: number; shown: number }; // shown > k = nhóm hoà vắt mốc K hiện cả nhóm

export type PipelineResult = {
  way: Way; // cách chia đã chạy: mã chunk của mọi danh sách dưới đây thuộc cách chia này
  candidates: number[]; // sau lọc metadata
  retrieval: RetrievalResult;
  rerank: ReorderStep | null;
  haikuFilter: FilterStep | null;
  nearDuplicate: FilterStep | null;
  mmr: ReorderStep | null; // input = khối MMR thật sự xếp (khối đã rerank khi có rerank)
  final: Row[] | null; // danh sách cuối, TRƯỚC khi cắt top-K; null = "in progress"
  cut: TopKCut | null;
  emptyAfter: StepCode | null;
  removedAt: Map<number, RemovingStep>; // chunk không có trong danh sách cuối → bước đã loại nó
};

// Câu tự gõ: không rerank, không lọc Haiku (không có điểm tính sẵn, Luật chung 9); trang phải tắt các
// lựa chọn đó, nên cấu hình khác là lỗi lập trình (như `retrievalPlan`).
function checkConfig(config: PipelineConfig, freeQuery: boolean): void {
  if (freeQuery && (config.rerank !== "none" || config.haikuFilter)) {
    throw new Error("a typed question has no stored rerank or Haiku scores");
  }
  position(config.topK, TOP_K_RANGE[0], TOP_K_RANGE[1]);
  position(config.topN, TOP_N_RANGE[0], TOP_N_RANGE[1]);
  position(config.lambda, 0, 100);
  position(config.nearDuplicateThreshold, 50, 100);
}

export function runPipeline(
  demo: DemoFile,
  index: WayIndex,
  query: Query,
  config: PipelineConfig,
): PipelineResult {
  const question: Question | null = "question" in query ? query.question : null;
  checkConfig(config, question === null);
  const way = config.way;
  const candidates = metadataCandidates(demo, way, config.metadata);
  const retrieval = retrieve(demo, index, query, config, candidates);
  const result: PipelineResult = {
    way,
    candidates,
    retrieval,
    rerank: null,
    haikuFilter: null,
    nearDuplicate: null,
    mmr: null,
    final: null,
    cut: null,
    emptyAfter: retrieval.emptyAfter,
    removedAt: new Map(),
  };
  // "in progress" thắng mọi trạng thái của bước đứng trước (Luật chung 8)
  if (retrieval.list === null) return result;
  const kept = new Set(candidates);
  const found = new Set(retrieval.list.map((row) => row.chunk));
  for (const chunk of demo.ways[way].map((c) => c.id)) {
    // Đoạn còn sau lọc mà vắng ở danh sách tìm: chỉ danh sách BM25 bỏ đoạn (điểm 0) → "not found"
    if (!kept.has(chunk)) result.removedAt.set(chunk, "metadata");
    else if (!found.has(chunk)) result.removedAt.set(chunk, "bm25");
  }
  let rows = toRows(retrieval.list);
  if (rows.length > 0 && config.rerank !== "none" && question !== null) {
    const rerank = config.rerank === "cross_encoder" ? rerankCrossEncoder : rerankHaiku;
    const output = rerank(demo, question, way, rows, config.topN);
    result.rerank = { input: rows, output };
    rows = output;
  }
  if (rows.length > 0 && config.haikuFilter && question !== null) {
    const step = haikuFilter(demo, question, way, rows);
    result.haikuFilter = step;
    for (const chunk of step.dropped) result.removedAt.set(chunk, "haiku-filter");
    rows = step.rows;
    if (rows.length === 0) result.emptyAfter = "haiku-filter";
  }
  if (rows.length > 0 && config.nearDuplicate) {
    const step = nearDuplicateFilter(demo, way, rows, config.nearDuplicateThreshold);
    result.nearDuplicate = step;
    for (const chunk of step.dropped) result.removedAt.set(chunk, "near-duplicate");
    rows = step.rows;
  }
  if (rows.length > 0 && config.mmr) {
    // Khi có rerank: chỉ khối đã rerank, đuôi "not reranked" giữ nguyên phía sau
    const { block, rest } = splitReranked(rows);
    const output = mmr(demo, way, block, config.lambda);
    result.mmr = { input: block, output };
    rows = [...output, ...rest];
  }
  result.final = rows;
  result.cut = topKCut(rows, config.topK);
  return result;
}

// Cắt top-K để hiển thị: nhóm hoà vắt mốc K hiện cả nhóm, các dòng sau K mang nhãn "tied across the cut".
export function topKCut(rows: readonly Row[], k: number): TopKCut {
  position(k, TOP_K_RANGE[0], TOP_K_RANGE[1]);
  if (k >= rows.length) return { k, shown: rows.length };
  return { k, shown: Math.max(k, rows[k - 1].tiedTo) };
}

// Mũi tên của một bước xếp lại (rerank, MMR), theo thứ tự `output`: vị trí vào − vị trí ra (dương = lên
// hạng); null = không vẽ — đuôi "not reranked", hoặc khoảng hạng vào và ra chồng nhau (chưa chắc đã đổi).
export function arrows(step: ReorderStep): (number | null)[] {
  const before = new Map(step.input.map((row) => [row.chunk, row]));
  return step.output.map((row) => {
    if (row.notReranked) return null;
    const input = before.get(row.chunk);
    if (input === undefined) throw new Error(`chunk ${row.chunk} is not in the step input`);
    const moved = !overlaps([input.tiedFrom, input.tiedTo], [row.tiedFrom, row.tiedTo]);
    return moved ? input.rank - row.rank : null;
  });
}
