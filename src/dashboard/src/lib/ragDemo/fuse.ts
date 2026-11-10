// Gộp câu con và trộn BM25 + dense của demo RAG (ADR-0041, bảng từng bước; Luật chung 4–6).
// Điểm vào là điểm đã làm tròn của bước trước; giá trị trung gian giữ số thực 64 bit; mọi phép cộng
// nhiều số hạng đi theo thứ tự cố định (Luật chung 5), để test Python tính lại khớp từng bit.
import { averageRank, rankRange, slider } from "./rank.ts";
import type { RankedChunk, ScoredChunk } from "./rank.ts";

// Bài gốc (Cormack, Clarke & Büttcher, SIGIR 2009) và mặc định `rank_constant` của Elasticsearch.
export const RRF_K = 60;

// Σ 1 / (k + r) theo thứ tự danh sách; r = hạng trung bình của nhóm hoà. Đoạn vắng ở một danh sách
// góp 0 (BM25 điểm 0 không có hạng), nên chỉ đoạn có hạng ở ít nhất một danh sách được xếp.
function rrf(lists: readonly (readonly RankedChunk[])[]): RankedChunk[] {
  const totals = new Map<number, number>();
  for (const list of lists) {
    for (const row of list) {
      totals.set(row.chunk, (totals.get(row.chunk) ?? 0) + 1 / (RRF_K + averageRank(row)));
    }
  }
  return rankRange([...totals].map(([chunk, score]) => ({ chunk, score })));
}

// Gộp câu con (RAG-Fusion): luôn RRF, kể cả khi chỉ có 1 câu con, để thang điểm không đổi theo số câu
// con (Luật chung 4). `lists` theo thứ tự câu con trong file (expand / step-back: câu gốc trước).
// Mọi câu con rỗng → danh sách rỗng ("no passages left after: sub-query merge", Luật chung 6).
export function mergeSubQueries(lists: readonly (readonly RankedChunk[])[]): RankedChunk[] {
  return rrf(lists);
}

// Trộn RRF k = 60: BM25 trước dense. Một bên rỗng góp 0 (Luật chung 6).
export function fuseRrf(bm25: readonly RankedChunk[], dense: readonly RankedChunk[]): RankedChunk[] {
  return rrf([bm25, dense]);
}

// Điểm của mỗi chunk trong tập chuẩn hoá theo thứ tự mã chunk; chunk không có trong danh sách (BM25
// điểm 0, hoặc tổng 0 sau gộp câu con) mang điểm 0 — tập chuẩn hoá là mọi chunk còn lại.
function scoresOver(list: readonly RankedChunk[], chunks: readonly number[]): number[] {
  const byChunk = new Map(list.map((row) => [row.chunk, row.score]));
  return chunks.map((chunk) => byChunk.get(chunk) ?? 0);
}

function sortedChunks(candidates: readonly number[]): number[] {
  return [...candidates].sort((a, b) => a - b);
}

// min-max (x − min) / (max − min); max = min → 0 (lựa chọn thiết kế: danh sách không phân biệt gì thì
// không góp vào điểm trộn).
function minMax(values: readonly number[]): number[] {
  let low = Infinity;
  let high = -Infinity;
  for (const value of values) {
    if (value < low) low = value;
    if (value > high) high = value;
  }
  if (high === low) return values.map(() => 0);
  return values.map((value) => (value - low) / (high - low));
}

// α·m(dense) + (1 − α)·m(BM25), cộng BM25 trước; `alphaHundredths` = vị trí thanh kéo (mặc định 50).
export function fuseWeighted(
  bm25: readonly RankedChunk[],
  dense: readonly RankedChunk[],
  candidates: readonly number[],
  alphaHundredths: number,
): RankedChunk[] {
  const chunks = sortedChunks(candidates);
  const alpha = slider(alphaHundredths);
  const bm25Norm = minMax(scoresOver(bm25, chunks));
  const denseNorm = minMax(scoresOver(dense, chunks));
  const entries: ScoredChunk[] = chunks.map((chunk, i) => ({
    chunk,
    score: alpha.complement * bm25Norm[i] + alpha.value * denseNorm[i],
  }));
  return rankRange(entries);
}

// DBSF theo Qdrant (`lib/segment/src/common/score_fusion.rs`): (x − (μ − 3σ)) / (6σ), σ mẫu, không kẹp;
// mọi điểm bằng nhau (so điểm đã làm tròn, không so σ = 0) hoặc 1 phần tử → 0,5. μ, σ tính 2 lượt theo
// thứ tự mã chunk, chia sau khi cộng (Qdrant: 1 lượt Welford, số 32 bit).
function distributionNorm(values: readonly number[]): number[] {
  const n = values.length;
  if (n <= 1 || values.every((value) => value === values[0])) return values.map(() => 0.5);
  let acc = 0;
  for (const value of values) acc = acc + value;
  const mu = acc / n;
  let acc2 = 0;
  for (const value of values) {
    const d = value - mu;
    acc2 = acc2 + d * d;
  }
  const sigma = Math.sqrt(acc2 / (n - 1));
  return values.map((value) => (value - (mu - 3 * sigma)) / (6 * sigma));
}

export function fuseDbsf(
  bm25: readonly RankedChunk[],
  dense: readonly RankedChunk[],
  candidates: readonly number[],
): RankedChunk[] {
  const chunks = sortedChunks(candidates);
  const bm25Norm = distributionNorm(scoresOver(bm25, chunks));
  const denseNorm = distributionNorm(scoresOver(dense, chunks));
  return rankRange(chunks.map((chunk, i) => ({ chunk, score: bm25Norm[i] + denseNorm[i] })));
}
