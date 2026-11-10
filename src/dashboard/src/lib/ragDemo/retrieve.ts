// Bước tìm của demo RAG: câu con theo cách biến đổi câu hỏi, BM25 / dense, gộp câu con, trộn
// (ADR-0041 Luật chung 1, 4, 6, 8, 9). Lọc metadata đứng trước bước này: nó chỉ quyết `candidates`.
import { buildChunkIndex, DEFAULT_BM25, searchBm25 } from "./bm25.ts";
import type { Bm25Params, ChunkIndex } from "./bm25.ts";
import type { DemoFile, Question, Way } from "./demoFile.ts";
import { fuseDbsf, fuseRrf, fuseWeighted, mergeSubQueries } from "./fuse.ts";
import { allChunks, rankRange } from "./rank.ts";
import type { RankedChunk } from "./rank.ts";

// 7 lựa chọn của ADR-0037 D7, kể cả "không biến đổi".
export const TRANSFORMS = [
  "none",
  "rewrite",
  "expand",
  "hyde",
  "multi_query",
  "decompose",
  "step_back",
] as const;
export type Transform = (typeof TRANSFORMS)[number];
export type Retriever = "bm25" | "dense" | "hybrid";
export type Fusion = "rrf" | "weighted" | "dbsf";

export type RetrievalConfig = {
  way: Way;
  retriever: Retriever;
  fusion: Fusion;
  alpha: number; // vị trí thanh kéo α (phần trăm), mặc định 50
  transform: Transform;
  context: boolean; // công tắc câu ngữ cảnh
  bm25: Bm25Params;
};

// Mặc định khi mở trang (ADR-0041): hybrid RRF, không biến đổi, câu ngữ cảnh tắt, recursive 500.
export const DEFAULT_RETRIEVAL: RetrievalConfig = {
  way: "recursive_500",
  retriever: "hybrid",
  fusion: "rrf",
  alpha: 50,
  transform: "none",
  context: false,
  bm25: DEFAULT_BM25,
};

// Biến đổi đi qua bước gộp câu con (RRF); rewrite / HyDE thay câu gốc, không gộp (Luật chung 4).
const MERGED: ReadonlySet<Transform> = new Set(["expand", "step_back", "multi_query", "decompose"]);

// Câu con theo thứ tự cộng: expand / step-back = câu gốc rồi câu biến đổi; multi-query / decompose =
// đúng các câu Haiku viết, không thêm câu gốc (Thy chọn, như `include_original=False` của LangChain).
export function subQueries(question: Question, transform: Transform): string[] {
  const t = question.transforms;
  switch (transform) {
    case "none":
      return [question.text];
    case "rewrite":
      return [t.rewrite];
    case "hyde":
      return [t.hyde];
    case "expand":
      return [question.text, t.expand];
    case "step_back":
      return [question.text, t.step_back];
    case "multi_query":
      return [...t.multi_query];
    case "decompose":
      return [...t.decompose];
  }
}

// Ở cách "không chia" chunk đã là cả bài nên công tắc coi là tắt (ADR-0039 D2, Luật chung 8).
export function contextEffective(way: Way, context: boolean): boolean {
  return context && way !== "whole";
}

// Chuỗi BM25 thấy: câu ngữ cảnh (chữ gốc, không phải `context_en`), xuống dòng, chunk; `context` null →
// chunk trần (Anthropic "Contextual Retrieval", 2024).
export function chunkTexts(demo: DemoFile, way: Way, context: boolean): string[] {
  const withContext = contextEffective(way, context);
  return demo.ways[way].map((chunk) => {
    const passage = demo.passages[chunk.passage];
    return withContext && passage.context !== null
      ? `${passage.context}\n${passage.text}`
      : passage.text;
  });
}

// Index BM25 trên mọi chunk của cách chia (thống kê của cả kho, kể cả khi lọc). Trang giữ sẵn theo
// (cách chia, công tắc có hiệu lực).
export function buildWayIndex(demo: DemoFile, way: Way, context: boolean): ChunkIndex {
  return buildChunkIndex(chunkTexts(demo, way, context));
}

export type RetrievalStatus = "ok" | "bm25-only" | "in-progress";
export type RetrievalPlan = {
  bm25: boolean;
  dense: "run" | "pending" | "off";
  fuse: boolean;
  status: RetrievalStatus; // "bm25-only" = "hybrid rơi về BM25"; "in-progress" = "dense trần cần phần còn chờ"
};

// Theo cấu hình, trước khi chạy (Thy chọn, Luật chung 8): dense của câu biến đổi và của chunk kèm câu
// ngữ cảnh còn chờ (`provenance.pending`). Câu tự gõ: chỉ BM25, không biến đổi (Luật chung 9) — trang
// phải tắt các lựa chọn đó, nên cấu hình khác là lỗi lập trình.
export function retrievalPlan(config: RetrievalConfig, freeQuery: boolean = false): RetrievalPlan {
  if (freeQuery && (config.retriever !== "bm25" || config.transform !== "none")) {
    throw new Error("a typed question runs BM25 only, without a question transform");
  }
  const needsPending = config.transform !== "none" || contextEffective(config.way, config.context);
  if (config.retriever === "bm25") return { bm25: true, dense: "off", fuse: false, status: "ok" };
  if (config.retriever === "dense") {
    return needsPending
      ? { bm25: false, dense: "pending", fuse: false, status: "in-progress" }
      : { bm25: false, dense: "run", fuse: false, status: "ok" };
  }
  return needsPending
    ? { bm25: true, dense: "pending", fuse: false, status: "bm25-only" }
    : { bm25: true, dense: "run", fuse: true, status: "ok" };
}

export type SubQueryResult = {
  text: string;
  mode: "accented" | "folded" | null; // chế độ dấu BM25 của câu con (ADR-0038 D3); null ở dense
  ranked: RankedChunk[];
};
export type RetrieverBlock = {
  subQueries: SubQueryResult[];
  merged: RankedChunk[] | null; // null khi biến đổi không qua bước gộp câu con
  list: RankedChunk[]; // danh sách bộ tìm đưa sang bước sau
};
// Bước đầu tiên ra danh sách rỗng (Luật chung 6); trang ghi "no passages left after: <bước>".
export type RetrievalStep = "metadata filter" | "bm25" | "dense" | "sub-query merge" | "fusion";
export type RetrievalResult = {
  plan: RetrievalPlan;
  bm25: RetrieverBlock | null;
  dense: RetrieverBlock | null; // null khi tắt hoặc còn chờ
  fused: RankedChunk[] | null;
  list: RankedChunk[] | null; // null = "in progress", không có danh sách
  emptyAfter: RetrievalStep | null;
};

export type Query = { question: Question } | { freeText: string };

function bm25Block(
  index: ChunkIndex,
  texts: readonly string[],
  merge: boolean,
  params: Bm25Params,
  candidates: readonly number[],
): RetrieverBlock {
  const subs = texts.map((text) => {
    const result = searchBm25(index, text, params, candidates);
    return { text, mode: result.mode, ranked: result.ranked };
  });
  const merged = merge ? mergeSubQueries(subs.map((sub) => sub.ranked)) : null;
  return { subQueries: subs, merged, list: merged ?? subs[0].ranked };
}

// Dense chỉ chạy khi không biến đổi và không có câu ngữ cảnh (retrievalPlan), nên một câu con:
// điểm cosine tính sẵn trong file theo passage.
function denseBlock(
  demo: DemoFile,
  question: Question,
  way: Way,
  candidates: readonly number[],
): RetrieverBlock {
  const chunks = demo.ways[way];
  const ranked = rankRange(
    candidates.map((chunk) => ({ chunk, score: question.dense[chunks[chunk].passage] })),
  );
  return { subQueries: [{ text: question.text, mode: null, ranked }], merged: null, list: ranked };
}

function emptyStep(block: RetrieverBlock, single: RetrievalStep): RetrievalStep | null {
  if (block.list.length > 0) return null;
  return block.merged === null ? single : "sub-query merge";
}

// Chạy bước tìm tới hết bước trộn. `index` = buildWayIndex(demo, config.way, config.context);
// `candidates` = chunk còn lại sau lọc metadata (mặc định mọi chunk).
export function retrieve(
  demo: DemoFile,
  index: ChunkIndex,
  query: Query,
  config: RetrievalConfig,
  candidates?: readonly number[],
): RetrievalResult {
  const question = "question" in query ? query.question : null;
  const plan = retrievalPlan(config, question === null);
  const pool = candidates ?? allChunks(demo.ways[config.way].length);
  if (plan.status === "in-progress") {
    return { plan, bm25: null, dense: null, fused: null, list: null, emptyAfter: null };
  }
  // Lọc metadata loại hết đoạn: bước làm rỗng là bước lọc, không phải bước tìm (Luật chung 6);
  // "in progress" ở trên vẫn thắng (Luật chung 8).
  if (pool.length === 0) {
    return { plan, bm25: null, dense: null, fused: null, list: [], emptyAfter: "metadata filter" };
  }
  const texts =
    question === null ? [(query as { freeText: string }).freeText] : subQueries(question, config.transform);
  const merge = MERGED.has(config.transform);
  const bm25 = plan.bm25 ? bm25Block(index, texts, merge, config.bm25, pool) : null;
  const dense =
    plan.dense === "run" && question !== null ? denseBlock(demo, question, config.way, pool) : null;
  if (bm25 !== null && dense !== null) {
    const fused =
      config.fusion === "rrf"
        ? fuseRrf(bm25.list, dense.list)
        : config.fusion === "weighted"
          ? fuseWeighted(bm25.list, dense.list, pool, config.alpha)
          : fuseDbsf(bm25.list, dense.list, pool);
    // Một bộ tìm rỗng thì trộn vẫn chạy với bộ kia; chỉ dừng khi cả hai rỗng (Luật chung 6).
    const empty = bm25.list.length === 0 && dense.list.length === 0;
    return { plan, bm25, dense, fused, list: fused, emptyAfter: empty ? "fusion" : null };
  }
  const block = (bm25 ?? dense) as RetrieverBlock;
  const emptyAfter = emptyStep(block, bm25 !== null ? "bm25" : "dense");
  return { plan, bm25, dense, fused: null, list: block.list, emptyAfter };
}
