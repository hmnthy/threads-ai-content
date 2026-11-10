// Xếp hạng chung cho mọi bước có điểm liên tục của demo RAG (ADR-0041 Luật chung 2, 5).
// Chỉ dùng cú pháp TypeScript xoá được: test Python chạy đúng file này bằng `node --experimental-strip-types`.

// Hoà = bằng nhau sau khi làm tròn tới số chữ số này (ADR-0038 D4). Làm tròn thay vì so ngưỡng chênh
// lệch vì ngưỡng không bắc cầu: A hoà B, B hoà C mà A không hoà C. Bản Python:
// `src/rag_demo/demo_file.py:71#SCORE_DECIMALS`; bộ đọc file từ chối file ghi số khác (`demoFile.ts`).
export const SCORE_DECIMALS = 6;

// Điểm xuất của mọi bước (ADR-0041 Luật chung 5): giá trị đúng nửa ô làm tròn ra xa số 0 (`toFixed`);
// `+ 0` đổi −0 thành 0, như `_score` của Python.
export function roundScore(value: number): number {
  return Number(value.toFixed(SCORE_DECIMALS)) + 0;
}

export type RankedChunk = {
  chunk: number; // mã chunk gốc của cách chia (vị trí trong `ways[way]`), dùng để phá hoà
  score: number; // đã làm tròn SCORE_DECIMALS
  rank: number; // vị trí từ 1, sau khi phá hoà theo mã chunk
  tiedFrom: number; // tiedFrom < tiedTo = chunk này hoà, hạng thật là cả khoảng
  tiedTo: number;
};

export type ScoredChunk = { chunk: number; score: number };

// Xếp mọi đoạn, kể cả điểm ≤ 0: điểm giảm dần, hoà theo điểm đã làm tròn, phá hoà theo mã chunk gốc
// (không theo vị trí trong danh sách vào, nên kết quả không đổi khi danh sách vào đã bị lọc / xáo).
export function rankRange(entries: readonly ScoredChunk[]): RankedChunk[] {
  const rows = entries
    .map((entry) => ({ chunk: entry.chunk, score: roundScore(entry.score) }))
    .sort((a, b) => b.score - a.score || a.chunk - b.chunk);
  const ranked: RankedChunk[] = [];
  let start = 0;
  while (start < rows.length) {
    let end = start;
    while (end + 1 < rows.length && rows[end + 1].score === rows[start].score) end += 1;
    for (let i = start; i <= end; i += 1) {
      ranked.push({ ...rows[i], rank: i + 1, tiedFrom: start + 1, tiedTo: end + 1 });
    }
    start = end + 1;
  }
  return ranked;
}

export function allChunks(count: number): number[] {
  return Array.from({ length: count }, (_, chunk) => chunk);
}

// Riêng BM25: đoạn có điểm sau làm tròn bằng 0 không được xếp hạng (đoạn không khớp từ nào luôn
// thuộc nhóm này, ADR-0038 D4); `candidates` = các chunk còn lại sau lọc metadata.
export function rankBm25(scores: readonly number[], candidates?: readonly number[]): RankedChunk[] {
  const chunks = candidates ?? allChunks(scores.length);
  return rankRange(
    chunks
      .map((chunk) => ({ chunk, score: roundScore(scores[chunk]) }))
      .filter((entry) => entry.score > 0),
  );
}

// Hạng trung bình của nhóm hoà (fractional ranking, như `scipy.stats.rankdata(method="average")`),
// là r đưa vào RRF (ADR-0041, bảng từng bước).
export function averageRank(row: RankedChunk): number {
  return (row.tiedFrom + row.tiedTo) / 2;
}

// Thanh kéo lưu số nguyên i (phần trăm); giá trị = i / 100 và phần bù = (100 − i) / 100, để bước 0,1
// không thành 0,30000000000000004 (ADR-0041 Luật chung 5).
export type SliderValue = { value: number; complement: number };

export function slider(hundredths: number): SliderValue {
  if (!Number.isInteger(hundredths) || hundredths < 0) {
    throw new RangeError(`slider position must be a non-negative integer, got ${hundredths}`);
  }
  return { value: hundredths / 100, complement: (100 - hundredths) / 100 };
}
