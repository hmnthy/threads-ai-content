import type { Noun, testVerdict } from "@/lib/landing";

// Nhãn kết quả của 1 phép so (Thy chốt 2026-10-29, ý b) — MỘT nguồn cho bảng 33 phép so, chú giải,
// panel engagement của /topics (thẻ mobile, dòng đọc, aria-label) và mục "Result of a row". Hai nhãn
// "không kết luận" phải khác nhau thấy được: ● (tô đặc) và ◌ (vòng chấm, trong pill nền xám).
export type Verdict = ReturnType<typeof testVerdict>;

export function tooFewLabel(noun: Noun, minPosts: number): string {
  return `Too few ${noun.many} (n < ${minPosts}): not concluded`;
}

export function verdictParts(verdict: Verdict, minPosts: number, noun: Noun) {
  switch (verdict) {
    case "higher":
      return { mark: "▲", text: "Stood out above", tone: "font-semibold text-amber-700" };
    case "lower":
      return { mark: "▼", text: "Stood out below", tone: "font-semibold text-amber-700" };
    case "not distinguishable":
      return { mark: "●", text: "Not significant after correction", tone: "text-text-primary" };
    case "too few posts":
      return { mark: "◌", text: tooFewLabel(noun, minPosts), tone: "text-text-muted" };
    default:
      return { mark: "—", text: "Not tested", tone: "text-text-muted" };
  }
}

export function VerdictMark({ verdict }: { verdict: Verdict }) {
  const mark = verdictParts(verdict, 0, { one: "", many: "" });
  return (
    <span
      aria-hidden="true"
      className={`inline-flex w-4 shrink-0 justify-center text-[12px] leading-none ${
        verdict === "not distinguishable" ? "text-text-secondary" : mark.tone
      }`}
    >
      {mark.mark}
    </span>
  );
}

// Nhãn đầy đủ (ký hiệu + chữ); "too few" nằm trong pill nền xám để cả ô khác hẳn "not significant"
export function VerdictLabel({ verdict, minPosts, noun }: { verdict: Verdict; minPosts: number; noun: Noun }) {
  const v = verdictParts(verdict, minPosts, noun);
  return (
    <span
      className={`inline-flex items-baseline gap-1.5 text-[13px] leading-[1.45] ${v.tone} ${
        verdict === "too few posts" ? "rounded-md bg-bg-surface px-1.5 py-0.5" : ""
      }`}
    >
      <VerdictMark verdict={verdict} />
      <span>{v.text}</span>
    </span>
  );
}
