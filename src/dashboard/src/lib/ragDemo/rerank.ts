// Rerank top-N của demo RAG (ADR-0041, bảng từng bước; Luật chung 2, 3, 7): cross-encoder hoặc Haiku,
// luôn chấm theo câu hỏi gốc (file chỉ có điểm đó). Đoạn ngoài khối giữ nguyên làm đuôi "not reranked".
import type { DemoFile, Question, Way } from "./demoFile.ts";
import { haikuScore } from "./filters.ts";
import { position, rankRange } from "./rank.ts";
import type { Row } from "./rank.ts";

export type Rerank = "none" | "cross_encoder" | "haiku";

// Thanh kéo N: 5–50 bước 5, mặc định 20 (lựa chọn thiết kế).
export const TOP_N_DEFAULT = 20;
export const TOP_N_RANGE = [5, 50] as const;

// Cỡ khối rerank: N đầu tiên, nhóm hoà vắt mốc N vào cả nhóm; N ≥ độ dài → cả danh sách.
export function rerankBlockSize(rows: readonly Row[], n: number): number {
  position(n, TOP_N_RANGE[0], TOP_N_RANGE[1]);
  if (n >= rows.length) return rows.length;
  return rows[n - 1].tiedTo;
}

// Đuôi: giữ điểm, nhóm hoà, khoảng hạng của bước trước (vị trí không đổi vì khối đã lấy trọn nhóm vắt
// mốc N).
function tail(rows: readonly Row[], size: number): Row[] {
  return rows.slice(size).map((row) => ({ ...row, notReranked: true }));
}

// Cross-encoder: logit thô theo passage của chunk; hoà theo Luật chung 2 trong khối đã rerank.
export function rerankCrossEncoder(
  demo: DemoFile,
  question: Question,
  way: Way,
  rows: readonly Row[],
  n: number,
): Row[] {
  const size = rerankBlockSize(rows, n);
  const chunks = demo.ways[way];
  const block = rankRange(
    rows
      .slice(0, size)
      .map((row) => ({ chunk: row.chunk, score: question.cross_encoder[chunks[row.chunk].passage] })),
  );
  const head: Row[] = block.map((row) => ({ ...row, notReranked: false, tiedAtPick: null }));
  return [...head, ...tail(rows, size)];
}

// Haiku: sắp xếp ổn định theo điểm 0–3, cùng điểm giữ thứ tự bước trước (Luật chung 3). Khoảng hạng chỉ
// khi cùng điểm Haiku VÀ cùng nhóm hoà ở bước trước: khoảng = các vị trí mới nhóm đó chiếm (liền nhau
// vì sắp xếp ổn định). Haiku xếp mọi ứng viên trong khối, kể cả điểm dưới mức giữ (nhãn keep / drop).
export function rerankHaiku(
  demo: DemoFile,
  question: Question,
  way: Way,
  rows: readonly Row[],
  n: number,
): Row[] {
  const size = rerankBlockSize(rows, n);
  const scored = rows.slice(0, size).map((row) => ({
    row,
    score: haikuScore(demo, question, way, row.chunk),
  }));
  scored.sort((a, b) => b.score - a.score); // Array.prototype.sort ổn định (ES2019)
  const head: Row[] = [];
  let start = 0;
  while (start < scored.length) {
    let end = start;
    const same = (i: number) =>
      scored[i].score === scored[start].score &&
      scored[i].row.tiedFrom === scored[start].row.tiedFrom &&
      scored[i].row.tiedTo === scored[start].row.tiedTo;
    while (end + 1 < scored.length && same(end + 1)) end += 1;
    for (let i = start; i <= end; i += 1) {
      head.push({
        chunk: scored[i].row.chunk,
        score: scored[i].score,
        rank: i + 1,
        tiedFrom: start + 1,
        tiedTo: end + 1,
        notReranked: false,
        tiedAtPick: null,
      });
    }
    start = end + 1;
  }
  return [...head, ...tail(rows, size)];
}

// Khối đã rerank (đầu danh sách) và đuôi "not reranked".
export function splitReranked(rows: readonly Row[]): { block: Row[]; rest: Row[] } {
  const cut = rows.findIndex((row) => row.notReranked);
  return cut < 0
    ? { block: [...rows], rest: [] }
    : { block: rows.slice(0, cut), rest: rows.slice(cut) };
}
