"use client";

import { useState, type ReactNode } from "react";
import { CaretDown } from "@phosphor-icons/react";

// Mảnh trình bày dùng chung của trang app tầng A. Thứ bậc chữ (Thy 2026-10-29, lần bác thứ 2: "headline
// / title khối thì bé, còn chữ nội dung thì lớn, dựa trên logic gì?") — tiêu đề LUÔN lớn hơn nội dung
// nó dẫn, để người đọc nhanh quét theo tiêu đề mà không sót khối (design-system §3, thang trang app):
//   40px w700  h1 tiêu đề trang (đầu trang căn giữa)
//   26px w700  h2 tiêu đề khối (kèm số thứ tự + dòng mục đích + kẻ đậm dưới)
//   20px w600  h3 tiêu đề mục trong khối
//   18px w600  câu trả lời của khối, trong khung nhấn
//   17px w600  h4 tiêu đề hộp con (Key numbers, How it is computed, Limits…)
//   15px       thân bài, gạch đầu dòng, nhãn hàng của bảng số; số chính 15px w700 (nhấn bằng độ đậm, không bằng cỡ)
//   13px       chữ trong ô bảng, ghi chú phụ
//   12.5px     mono: công thức, số trong bảng — chỉ mono
//   12px w600  header cột bảng, nhãn nhỏ (eyebrow "Answer")
//   0.8em      chỉ số dưới/trên trong Formula (≈ 10px) — không dùng ngoài công thức
export const TYPE = {
  h2: "text-[26px] font-bold leading-[1.25] tracking-[-0.02em] text-text-primary",
  h3: "text-[20px] font-semibold leading-[1.3] tracking-[-0.01em] text-text-primary",
  h4: "text-[17px] font-semibold leading-[1.4] text-text-primary",
  answer: "text-[18px] font-semibold leading-[1.45] text-text-primary",
  body: "text-[15px] leading-[1.6] text-text-secondary",
  bodyStrong: "text-[15px] font-semibold leading-[1.45] text-text-primary",
  cell: "text-[13px] leading-[1.45]",
  note: "text-[13px] leading-[1.55] text-text-secondary",
  mono: "font-mono text-[12.5px] leading-[1.7] tabular-nums",
  label: "text-[12px] font-medium leading-[1.5] text-text-muted",
  th: "text-[12px] font-semibold text-text-secondary",
  // Thy 2026-10-29: chữ chạy hết bề rộng khung chứa — không chừa khoảng trắng bên phải (bỏ giới hạn 72ch)
  measure: "",
} as const;

// Khối nội dung của trang: card riêng, đầu khối = số thứ tự + tiêu đề h2 + 1 câu mục đích, kẻ đậm ngăn
// đầu khối với thân. Mỗi khối một mục đích, thấy được khi lướt (Thy 2026-10-29)
export function Section({
  id,
  n,
  short,
  title,
  purpose,
  aside,
  children,
}: {
  id: string;
  n: string;
  short: string; // tên ngắn của khối — cùng chữ với dải mục lục đầu trang
  title: string;
  purpose: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="flex scroll-mt-6 flex-col gap-8 rounded-xl border border-border-hairline bg-bg-card px-5 py-7 sm:px-8 sm:py-8"
    >
      <header className="flex flex-col gap-2.5 border-b-2 border-text-primary pb-5">
        <span className="flex items-baseline gap-2">
          <span className="font-mono text-[12.5px] font-semibold text-amber-600">{n}</span>
          <span className="text-[12px] font-semibold tracking-[0.06em] text-text-muted">{short.toUpperCase()}</span>
        </span>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
          <h2 id={`${id}-title`} className={`m-0 ${TYPE.h2} [text-wrap:balance]`}>
            {title}
          </h2>
          {aside ? <span className="ml-auto">{aside}</span> : null}
        </div>
        <p className={`m-0 ${TYPE.body}`}>{purpose}</p>
      </header>
      {children}
    </section>
  );
}

// Mục trong khối: kẻ mảnh phía trên, tiêu đề h3 (+ 1 dòng ghi chú), rồi nội dung
export function SubSection({
  title,
  note,
  action,
  children,
}: {
  title: ReactNode;
  note?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 border-t border-border-hairline pt-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className={`m-0 ${TYPE.h3}`}>{title}</h3>
          {note ? <p className={`m-0 ${TYPE.note}`}>{note}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

// In đậm cụm then chốt trong chuỗi bằng `**…**` (Thy 2026-10-29: trang nhiều chữ cần điểm nhấn để đọc
// nhanh — dùng vừa đủ, 1 cụm mỗi ý là nhiều nhất)
export function rich(node: ReactNode): ReactNode {
  if (typeof node !== "string" || !node.includes("**")) return node;
  return node.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-semibold text-text-primary">
        {part}
      </strong>
    ) : (
      part
    ),
  );
}

// Gạch đầu dòng dọc, một ý một dòng; `tone="muted"` cho lớp chi tiết dưới ý chính
export function Bullets({ items, tone = "body" }: { items: ReactNode[]; tone?: "body" | "muted" }) {
  const shown = items.filter((item) => item !== null && item !== false && item !== "");
  if (shown.length === 0) return null;
  return (
    <ul
      className={`m-0 flex ${TYPE.measure} list-disc flex-col gap-1.5 pl-5 marker:text-text-muted ${
        tone === "body" ? TYPE.body : TYPE.note
      }`}
    >
      {shown.map((item, i) => (
        <li key={i}>{rich(item)}</li>
      ))}
    </ul>
  );
}

// Số chính, xếp dọc ở cột phải: mỗi số có nhãn, 1 dòng nghĩa và link tới định nghĩa — không số trần
export interface KeyNumber {
  value: string;
  label: string;
  note?: ReactNode;
  term?: string; // id mục trong "How every number on this page is computed" (anchor `term-<id>`)
}

const LINK =
  "underline decoration-text-muted decoration-dotted decoration-1 underline-offset-[3px] hover:text-amber-700 hover:decoration-amber-600 hover:decoration-solid";

export function KeyNumbers({ title = "Key numbers", items }: { title?: string; items: KeyNumber[] }) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-warm-border bg-warm-surface px-5 py-5">
      <h4 className={`m-0 ${TYPE.h4}`}>{title}</h4>
      <dl className="m-0 flex flex-1 flex-col justify-evenly gap-3.5">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex flex-col gap-0.5 border-t border-warm-border pt-3.5 first:border-t-0 first:pt-0"
          >
            <dt className="flex flex-wrap items-baseline gap-x-2.5">
              <span className="text-[15px] font-bold tabular-nums text-text-primary">{item.value}</span>
              {item.term ? (
                <a href={`#term-${item.term}`} className={`text-[15px] font-semibold text-text-primary ${LINK}`}>
                  {item.label}
                </a>
              ) : (
                <span className="text-[15px] font-semibold text-text-primary">{item.label}</span>
              )}
            </dt>
            {item.note ? <dd className={`m-0 ${TYPE.note}`}>{rich(item.note)}</dd> : null}
          </div>
        ))}
      </dl>
    </div>
  );
}

// Câu trả lời của khối: khung nhấn viền trái amber + nhãn "Answer" — tách khỏi tiêu đề và thân bài
export function Answer({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-r-xl border border-l-4 border-warm-border border-l-amber-600 bg-warm-surface px-5 py-4">
      <span className="text-[12px] font-semibold tracking-[0.06em] text-amber-700">ANSWER</span>
      <p className={`m-0 ${TYPE.answer} [text-wrap:pretty]`}>{children}</p>
    </div>
  );
}

// Câu trả lời + ý chính bên trái, số chính bên phải (cột phải có nội dung — không trống nửa card)
export function AnswerRow({
  answer,
  pointsTitle = "What to know",
  points,
  extra,
  keyNumbers,
  below,
}: {
  answer: ReactNode;
  pointsTitle?: string;
  points?: ReactNode[];
  extra?: ReactNode;
  keyNumbers?: KeyNumber[];
  below?: ReactNode; // khối dài trải hết bề rộng dưới 2 cột — không kéo cột trái dài hơn hộp số
}) {
  const hasPoints = points !== undefined && points.some((p) => p !== null && p !== false && p !== "");
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <div className="flex flex-col gap-5">
        <Answer>{answer}</Answer>
        {hasPoints ? (
          <div className="flex flex-col gap-2">
            <h4 className={`m-0 ${TYPE.h4}`}>{pointsTitle}</h4>
            <Bullets items={points} />
          </div>
        ) : null}
        {extra}
      </div>
      {keyNumbers && keyNumbers.length > 0 ? <KeyNumbers items={keyNumbers} /> : null}
      {below ? <div className="lg:col-span-2">{below}</div> : null}
    </div>
  );
}

// Link tới định nghĩa trong phần "How every number on this page is computed"
export function TermLink({ term, children }: { term: string; children: ReactNode }) {
  return (
    <a href={`#term-${term}`} className={`text-inherit ${LINK}`}>
      {children}
    </a>
  );
}

// Công thức 1 dòng: viết chỉ số kiểu LaTeX nhẹ — `x_i`, `x_(i)`, `x_{0.025}`, `R^d` — và component
// vẽ thành <sub>/<sup> thật. Không dùng ký tự chỉ số Unicode (ₙ, ᵢ…): IBM Plex Mono không có glyph,
// trình duyệt rơi về font khác, khó đọc ở 12.5px. Chỉ số không phải chữ/số (+, −) viết trong {}.
const SCRIPT = /([_^])(\{([^}]*)\}|\(([^)]*)\)|([\p{L}\p{N}]+))/gu;

export function Formula({ children }: { children: string }) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const match of children.matchAll(SCRIPT)) {
    const at = match.index ?? 0;
    if (at > last) parts.push(children.slice(last, at));
    const body = match[3] ?? (match[4] !== undefined ? `(${match[4]})` : match[5]);
    parts.push(
      match[1] === "_" ? (
        <sub key={at} className="text-[0.8em]">
          {body}
        </sub>
      ) : (
        <sup key={at} className="text-[0.8em]">
          {body}
        </sup>
      ),
    );
    last = at + match[0].length;
  }
  if (last < children.length) parts.push(children.slice(last));
  return <code className={`${TYPE.mono} whitespace-pre-wrap text-text-primary`}>{parts}</code>;
}

// Một bước phương pháp: tên + câu chữ thường, rồi công thức mono ngay dưới (lớp phụ, không đứng một mình)
export interface MethodStep {
  title: string;
  plain: ReactNode;
  formula?: string | string[]; // mảng = mỗi phương trình 1 dòng
}

// "Method and limits" — một mục h3 của khối, MỞ SẴN; nút thu gọn trông rõ là nút (viền + nền +
// chevron, 44px). Cách tính (từng bước, có công thức) rồi giới hạn, xếp dọc.
export function MethodSection({
  steps,
  limits,
  more,
}: {
  steps: MethodStep[];
  limits: ReactNode[];
  more?: ReactNode; // link tới phần công thức đầy đủ của trang
}) {
  const [open, setOpen] = useState(true);
  return (
    <SubSection
      title="Method and limits"
      note="How the numbers in this block are computed, and what they cannot tell."
      action={
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="inline-flex min-h-[44px] cursor-pointer items-center gap-2 rounded-full border border-border-hairline bg-bg-surface px-4 text-[13px] font-semibold text-text-primary hover:border-amber-600 hover:text-amber-700"
        >
          <CaretDown
            size={16}
            aria-hidden="true"
            className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`}
          />
          {open ? "Hide method and limits" : "Show method and limits"}
        </button>
      }
    >
      {open ? (
        // Xếp dọc: cách tính rồi giới hạn (Thy 2026-10-29: 2 cột song song khó đọc); nền xám nhạt = lớp kỹ
        // thuật, tách khỏi lớp kết quả (nền ấm) và lớp bằng chứng (nền trắng)
        <div className="flex flex-col gap-7 rounded-xl border border-border-hairline bg-bg-sunken px-3.5 py-5 sm:px-7 sm:py-6">
          <div className="flex flex-col gap-3">
            <h4 className={`m-0 ${TYPE.h4}`}>How it is computed</h4>
            <ol className="m-0 flex list-decimal flex-col gap-3 pl-4 marker:text-[15px] marker:font-semibold marker:text-text-muted sm:pl-5">
              {steps.map((step) => (
                <li key={step.title} className="sm:pl-1">
                  <div className="flex flex-col gap-1.5">
                    <span className={`${TYPE.measure} ${TYPE.body}`}>
                      <span className="font-semibold text-text-primary">{step.title}.</span> {step.plain}
                    </span>
                    {step.formula ? (
                      <span className="flex w-full flex-col rounded-md border border-border-hairline bg-bg-card px-3 py-1.5">
                        {(Array.isArray(step.formula) ? step.formula : [step.formula]).map((line) => (
                          <Formula key={line}>{line}</Formula>
                        ))}
                      </span>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </div>
          <div className="flex flex-col gap-2">
            <h4 className={`m-0 ${TYPE.h4}`}>Limits</h4>
            <Bullets items={limits} />
          </div>
          {more ? <span className={TYPE.note}>{more}</span> : null}
        </div>
      ) : null}
    </SubSection>
  );
}

// Chú giải cho nhãn kết quả: ký hiệu + tên + vì sao một dòng mang nhãn này
export function Legend({ items }: { items: { mark: ReactNode; name: string; rule: ReactNode }[] }) {
  return (
    <dl className="m-0 flex flex-col gap-2 rounded-xl border border-border-hairline bg-bg-sunken px-5 py-4">
      {items.map((item) => (
        <div key={item.name} className="grid grid-cols-[20px_minmax(0,1fr)] items-baseline gap-2">
          <dt className="flex justify-center">
            {item.mark}
            <span className="sr-only">{item.name}</span>
          </dt>
          <dd className={`m-0 ${TYPE.measure} ${TYPE.body}`}>
            <span className="font-semibold text-text-primary">{item.name}</span> — {item.rule}
          </dd>
        </div>
      ))}
    </dl>
  );
}
