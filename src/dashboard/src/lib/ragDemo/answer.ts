// Hạng của đáp án và so A/B của demo RAG (ADR-0041 mục "Hạng của đáp án").
import type { Question } from "./demoFile.ts";
import { REMOVING_STEPS } from "./pipeline.ts";
import type { PipelineResult, RemovingStep } from "./pipeline.ts";
import { groupsOf, overlaps } from "./rank.ts";
import type { Row } from "./rank.ts";
import type { RetrievalPlan } from "./retrieve.ts";

export type Outcome =
  | { kind: "rank"; from: number; to: number } // from = to: một hạng
  | { kind: "not-found" } // chỉ BM25 (điểm 0), kể cả khi rerank nhận danh sách thiếu đáp án
  | { kind: "filtered"; step: "metadata" | "haiku-filter" | "near-duplicate" }
  | { kind: "in-progress" }; // "dense trần cần phần còn chờ" (Luật chung 8)

export type GoldAnswer = {
  main: Outcome; // số chính: câu 1 bài = hạng bài đó; câu 3 / 7 = hạng của bài tìm thấy sau cùng
  units: Record<string, Outcome>; // theo `gold_unit_ids`
  bm25Only: boolean; // "hybrid rơi về BM25": nhãn "BM25 only", hạng vẫn tính như mọi cấu hình
};

// Trong top-K khi đầu khoảng ≤ K (khoảng vắt qua K tính là trong; ngoài K trang ghi "rank 30 (outside
// top 10)"). Hạng tính trên cả danh sách trước khi cắt.
export function insideTopK(outcome: Outcome, k: number): boolean {
  return outcome.kind === "rank" && outcome.from <= k;
}

function fromStep(step: RemovingStep): Outcome {
  return step === "bm25" ? { kind: "not-found" } : { kind: "filtered", step };
}

function stepOf(outcome: Outcome): number {
  if (outcome.kind === "not-found") return REMOVING_STEPS.indexOf("bm25");
  if (outcome.kind === "filtered") return REMOVING_STEPS.indexOf(outcome.step);
  throw new Error("only a missing unit has a removing step");
}

type Earliest = { group: number; from: number; to: number; hits: number };

// Nhóm sớm nhất chứa chunk trúng của mỗi bài; "nhóm" gồm cả nhóm 1 phần tử. Dòng MMR "tied at this
// pick" mang một hạng nên là nhóm 1 phần tử (ngoại lệ của mục "Hạng của đáp án").
function earliestGroups(rows: readonly Row[], hitsOf: Record<string, number[]>): Map<string, Earliest> {
  const owner = new Map<number, string>();
  for (const [unit, chunks] of Object.entries(hitsOf)) for (const c of chunks) owner.set(c, unit);
  const earliest = new Map<string, Earliest>();
  groupsOf(rows).forEach((group, index) => {
    const counts = new Map<string, number>();
    for (const row of group) {
      const unit = owner.get(row.chunk);
      if (unit !== undefined) counts.set(unit, (counts.get(unit) ?? 0) + 1);
    }
    for (const [unit, hits] of counts) {
      if (!earliest.has(unit)) {
        earliest.set(unit, { group: index, from: group[0].tiedFrom, to: group[0].tiedTo, hits });
      }
    }
  });
  return earliest;
}

// Công thức đóng của định nghĩa "[nhỏ nhất, lớn nhất] trên mọi cách xếp lại trong nhóm hoà": bài u ở
// nhóm sớm nhất [a_u, b_u] với c_u chunk trúng → [a_u, b_u − c_u + 1]. Số chính câu 3 / 7: đầu = max
// qua các nhóm g là nhóm sớm nhất của ít nhất một bài của (a_g + k_g − 1); cuối = max_u (b_u − c_u + 1).
// Cách chia đọc từ `result.way` (không truyền riêng), để mã chunk đáp án luôn khớp danh sách đã chạy.
export function goldAnswer(question: Question, result: PipelineResult): GoldAnswer | null {
  if (question.rule === "none") return null;
  const bm25Only = result.retrieval.plan.status === "bm25-only";
  const units: Record<string, Outcome> = {};
  if (result.final === null) {
    for (const unit of question.gold_unit_ids) units[unit] = { kind: "in-progress" };
    return { main: { kind: "in-progress" }, units, bm25Only };
  }
  const hitsOf = question.gold_chunks[result.way];
  const earliest = earliestGroups(result.final, hitsOf);
  for (const unit of question.gold_unit_ids) {
    const at = earliest.get(unit);
    if (at !== undefined) {
      units[unit] = { kind: "rank", from: at.from, to: at.to - at.hits + 1 };
      continue;
    }
    // Bước đã loại chunk trúng cuối cùng của bài = bước đứng sau nhất trong các bước đã loại chúng
    const steps = hitsOf[unit].map((chunk) => {
      const step = result.removedAt.get(chunk);
      if (step === undefined) throw new Error(`chunk ${chunk} is neither ranked nor removed`);
      return REMOVING_STEPS.indexOf(step);
    });
    units[unit] = fromStep(REMOVING_STEPS[Math.max(...steps)]);
  }
  const outcomes = question.gold_unit_ids.map((unit) => units[unit]);
  const missing = outcomes.filter((o) => o.kind !== "rank");
  let main: Outcome;
  if (missing.length > 0) {
    // Thiếu bài: số chính = trạng thái của bài thiếu; thiếu cả hai → trạng thái của bước đứng sau
    main = missing.reduce((a, b) => (stepOf(b) > stepOf(a) ? b : a));
  } else if (outcomes.length === 1) {
    main = outcomes[0];
  } else {
    const perGroup = new Map<number, { from: number; units: number }>();
    for (const at of earliest.values()) {
      const entry = perGroup.get(at.group) ?? { from: at.from, units: 0 };
      perGroup.set(at.group, { from: entry.from, units: entry.units + 1 });
    }
    const from = Math.max(...[...perGroup.values()].map((g) => g.from + g.units - 1));
    const to = Math.max(...outcomes.map((o) => (o as { to: number }).to));
    main = { kind: "rank", from, to };
  }
  return { main, units, bm25Only };
}

export type Side = { answer: GoldAnswer | null; plan: RetrievalPlan };
export type Verdict =
  | { kind: "no-verdict" } // câu không có đáp án (câu 10, câu tự gõ)
  | {
      kind: "no-clear-winner";
      reason: "in-progress" | "bm25-only" | "unranked" | "overlap";
      bm25OnlySide: "A" | "B" | null; // điều 3: bên "used BM25 only"
    }
  | { kind: "winner"; side: "A" | "B"; reason: "only-ranked" | "lower-rank" };

function noWinner(reason: "in-progress" | "bm25-only" | "unranked" | "overlap", side: "A" | "B" | null = null): Verdict {
  return { kind: "no-clear-winner", reason, bm25OnlySide: side };
}

// So A/B trên cùng một câu hỏi theo 5 điều của ADR-0041, xét theo thứ tự, dừng ở điều đầu tiên áp được.
// Điều 3 ("hybrid rơi về BM25") xét theo cấu hình (`plan`), không theo việc dense có thật sự ra danh
// sách (Luật chung 8).
export function compareAB(a: Side, b: Side): Verdict {
  if (a.answer === null || b.answer === null) return { kind: "no-verdict" };
  const ma = a.answer.main;
  const mb = b.answer.main;
  if (ma.kind === "in-progress" || mb.kind === "in-progress") return noWinner("in-progress");
  if (a.plan.status === "bm25-only" && b.plan.dense === "run") return noWinner("bm25-only", "A");
  if (b.plan.status === "bm25-only" && a.plan.dense === "run") return noWinner("bm25-only", "B");
  if (ma.kind !== "rank" && mb.kind !== "rank") return noWinner("unranked");
  if (ma.kind !== "rank") return { kind: "winner", side: "B", reason: "only-ranked" };
  if (mb.kind !== "rank") return { kind: "winner", side: "A", reason: "only-ranked" };
  if (overlaps([ma.from, ma.to], [mb.from, mb.to])) return noWinner("overlap");
  return { kind: "winner", side: ma.to < mb.from ? "A" : "B", reason: "lower-rank" };
}

// Điều 1 của A/B (câu không có đáp án): số đoạn còn lại, đếm TRƯỚC khi cắt top-K (null = "in progress")
// và đoạn đứng đầu danh sách cuối (null khi rỗng); nhãn "tied" đọc từ khoảng hạng / `tiedAtPick` của dòng.
export function listSummary(result: PipelineResult): { remaining: number | null; top: Row | null } {
  if (result.final === null) return { remaining: null, top: null };
  return { remaining: result.final.length, top: result.final[0] ?? null };
}
