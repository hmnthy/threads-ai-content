// MMR của demo RAG (Carbonell & Goldstein 1998; ADR-0041, bảng từng bước, Luật chung 5): chọn tham lam
// tới hết danh sách, giá trị = λ·rel − (1 − λ)·max cos(đoạn, đoạn đã chọn), lượt đầu phần phạt = 0.
import type { DemoFile, Way } from "./demoFile.ts";
import { cosineOf } from "./filters.ts";
import { minMax } from "./fuse.ts";
import { roundScore, slider } from "./rank.ts";
import type { Row } from "./rank.ts";

// λ mặc định 0,5 theo `lambda_mult` của LangChain; thanh kéo 0–1 bước 0,05.
export const LAMBDA_DEFAULT = 50;

// `rows` = danh sách vào MMR (khi có rerank: chỉ khối đã rerank — trang ghép đuôi phía sau). rel =
// điểm của bước chấm điểm gần nhất (điểm các dòng đang mang; bước lọc không đổi điểm), min-max về
// [0, 1], max = min → 0. Mỗi lượt: giá trị tính bằng số thực, làm tròn 6 chữ số CHỈ để so hoà; bằng
// nhau → đoạn đứng trước ở bước trước. Dòng ra mang một hạng (không khoảng), điểm = giá trị MMR lúc
// được chọn (đã làm tròn) và `tiedAtPick` = số đoạn khác cùng giá trị ở lượt đó.
export function mmr(demo: DemoFile, way: Way, rows: readonly Row[], lambdaHundredths: number): Row[] {
  const lambda = slider(lambdaHundredths);
  if (rows.length <= 1) return [...rows];
  const rel = minMax(rows.map((row) => row.score));
  const remaining = rows.map((row, i) => ({ row, rel: rel[i], penalty: 0 }));
  const picked: Row[] = [];
  while (remaining.length > 0) {
    const values = remaining.map((c) => roundScore(lambda.value * c.rel - lambda.complement * c.penalty));
    let best = 0;
    for (let i = 1; i < values.length; i += 1) if (values[i] > values[best]) best = i;
    const tied = values.filter((value) => value === values[best]).length - 1;
    const [choice] = remaining.splice(best, 1);
    const rank = picked.length + 1;
    picked.push({
      chunk: choice.row.chunk,
      score: values[best],
      rank,
      tiedFrom: rank,
      tiedTo: rank,
      notReranked: false,
      tiedAtPick: tied,
    });
    // phần phạt = max cosine với mọi đoạn đã chọn: cập nhật bằng đoạn vừa chọn
    for (const candidate of remaining) {
      const cosine = cosineOf(demo, way, choice.row.chunk, candidate.row.chunk);
      if (picked.length === 1 || cosine > candidate.penalty) candidate.penalty = cosine;
    }
  }
  return picked;
}
