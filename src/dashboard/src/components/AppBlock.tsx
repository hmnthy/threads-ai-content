"use client";

import { useState, type ReactNode } from "react";
import { CaretDown } from "@phosphor-icons/react";

// Mảnh trình bày dùng chung của mọi trang (landing lấy vai từ đây — design-system §3b C2). Thứ bậc chữ
// (Thy 2026-10-29, lần bác thứ 2: "headline / title khối thì bé, còn chữ nội dung thì lớn, dựa trên logic
// gì?") — tiêu đề LUÔN lớn hơn nội dung nó dẫn, để người đọc nhanh quét theo tiêu đề mà không sót khối
// (design-system §3, thang chung của sản phẩm — landing chỉ thêm display-1/2, ADR-0029):
//   40px w700  h1 tiêu đề trang (đầu trang căn giữa)
//   26px w700  h2 tiêu đề khối (kèm số thứ tự + dòng mục đích + kẻ đậm dưới)
//   20px w600  h3 tiêu đề mục trong khối
//   18px w600  câu trả lời của khối, trong khung nhấn
//   28px w700  số chính trong hộp Key numbers (vai metric, tabular — ADR-0030 K2)
//   17px w600  h4 tiêu đề hộp con (Key numbers, How it is computed, Limits…)
//   15px       thân bài, gạch đầu dòng, nhãn hàng của bảng số · nhãn dưới số trong hộp Key numbers (w600)
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
  metric: "text-[28px] font-bold leading-[1.15] tracking-[-0.02em] tabular-nums text-text-primary",
  eyebrow: "text-[12px] font-semibold tracking-[0.06em] text-text-muted",
  // Thy 2026-10-29: chữ chạy hết bề rộng khung chứa — không chừa khoảng trắng bên phải (bỏ giới hạn 72ch)
  measure: "",
} as const;

// Đầu trang app, dùng chung cho mọi trang (Thy 2026-10-31: Overview + Analytics căn giữa như Topics, ADR-0029 C2):
// eyebrow trang (label 12px amber) → h1 40px → câu hỏi của trang 18px → chip mốc dữ liệu → (tuỳ chọn) mục lục khối.
// Nội dung nằm trong cùng khung 1280px với Nav và <main> — thiếu khung thì trên màn hình rộng tiêu đề dạt mép trái
// `sections` = dải mục lục khối (số + tên ngắn, cùng chữ với nhãn trên tiêu đề mỗi khối) — thấy cả trang trong 1
// dòng, nhảy thẳng tới khối (Thy 2026-10-29: đọc nhanh không sót khối)
export type PageSection = readonly [id: string, n: string, label: string];

export function PageHeader({
  eyebrow,
  title,
  question,
  chips,
  sections,
  definition,
}: {
  eyebrow: string;
  title: string;
  question: ReactNode;
  chips?: ReactNode[];
  sections?: readonly PageSection[];
  definition?: ReactNode; // định nghĩa đơn vị đếm của trang, ngay dưới câu hỏi (B3: thuật ngữ định nghĩa trước khi dùng)
}) {
  const shown = (chips ?? []).filter((chip) => chip !== null && chip !== false && chip !== "");
  return (
    <header className="border-b border-border-hairline bg-bg-card">
      <div className="mx-auto flex w-full max-w-[1280px] flex-col items-center gap-4 px-6 pb-10 pt-12 text-center">
        <span className="text-[12px] font-semibold tracking-[0.14em] text-amber-700">{eyebrow.toUpperCase()}</span>
        <h1 className="m-0 text-[40px] font-bold leading-[1.1] tracking-[-0.025em] text-text-primary">{title}</h1>
        <p className="m-0 max-w-[720px] text-[18px] leading-[1.55] text-text-secondary [text-wrap:balance]">{question}</p>
        {definition ? <p className={`m-0 max-w-[720px] ${TYPE.body} [text-wrap:balance]`}>{rich(definition)}</p> : null}
        {shown.length > 0 ? (
          <p className="m-0 flex flex-wrap justify-center gap-2 font-mono text-[12.5px] text-text-secondary">
            {shown.map((chip, i) => (
              <span key={i} className="rounded-full border border-border-hairline bg-bg-sunken px-3 py-1">
                {chip}
              </span>
            ))}
          </p>
        ) : null}
        {sections && sections.length > 0 ? (
          <nav aria-label="Sections of this page" className="mt-4 w-full border-t border-border-hairline pt-6">
            <ol className="m-0 flex list-none flex-wrap justify-center gap-2 p-0">
              {sections.map(([id, n, label]) => (
                <li key={id}>
                  <a
                    href={`#${id}`}
                    className="inline-flex min-h-[44px] items-center gap-2 rounded-full border border-border-hairline bg-bg-card px-4 text-[15px] font-medium text-text-primary transition-colors hover:border-amber-600 hover:text-amber-700"
                  >
                    <span className="font-mono text-[12.5px] font-semibold text-amber-600">{n}</span>
                    {label}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
        ) : null}
      </div>
    </header>
  );
}

// Nhóm nút bật/tắt — MỘT kiểu cho mọi trang (ux-reviewer 2026-10-31: 3 kiểu toggle trên 3 trang, C2/C3): chọn = viền +
// nền amber nhạt, chưa chọn = viền mảnh + nền trắng (vẫn trông bấm được), 13px w600, vùng chạm 44px, `aria-pressed`
export function ToggleGroup<K extends string>({
  label,
  options,
  value,
  onChange,
  mono = false,
}: {
  label: string; // tên nhóm cho trình đọc màn hình
  options: readonly { key: K; label: string }[];
  value: K | null;
  onChange: (key: K) => void;
  mono?: boolean; // nhãn là số/mã (VD "30d") → mono 12.5px
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const on = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(option.key)}
            className={`inline-flex min-h-[44px] cursor-pointer items-center rounded-full border px-4 font-semibold transition-colors ${
              mono ? "font-mono text-[12.5px]" : "text-[13px]"
            } ${
              on
                ? "border-amber-600 bg-amber-soft text-amber-700"
                : "border-border-hairline bg-bg-card text-text-secondary hover:bg-bg-surface hover:text-text-primary"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

// Chữ gốc của 1 content unit (tiếng Việt / Pháp) không bao giờ đứng một mình (B2): dòng ngữ cảnh tiếng Anh nằm TRÊN
// chữ gốc, tiếng Anh đứng trước trong dòng, rồi "original language" (Thy 2026-11-01: người đọc tiếng Anh gặp ngữ cảnh
// trước, không phải đọc qua 5–9 dòng tiếng Việt). `topic`: tên topic; null = không thuộc topic nào trong lần gom cụm mới
// nhất (cùng tên "Unclustered" với trang Topics); undefined = chưa qua lần gom cụm nào. `topicCount` = số topic của lần
// gom cụm mới nhất. `size`: "body" 15px cho danh sách, "cell" 13px trong bảng (một cỡ cho mọi bảng).
// TOPIC_UNKNOWN = không đọc được thông tin topic lúc này: nhãn trung tính, không khẳng định gì (code-reviewer: "không
// biết" ≠ "rỗng"); `topicCount` null + chưa có khoá = kênh chưa gom cụm lần nào
export const TOPIC_UNKNOWN = Object.freeze({ topic: "unknown" } as const);
export type UnitTopic = string | null | undefined | typeof TOPIC_UNKNOWN;

// Tra topic của 1 content unit từ map phía server (`loadAppContext`) — một cách đọc cho mọi trang
export function topicOfUnit(topicOf: Record<string, string | null> | null, id: string): UnitTopic {
  if (topicOf === null) return TOPIC_UNKNOWN;
  return id in topicOf ? topicOf[id] : undefined;
}

export function UnitText({
  text,
  topic,
  topicCount = null,
  size = "body",
}: {
  text: string | null;
  topic: UnitTopic;
  topicCount?: number | null;
  size?: "body" | "cell";
}) {
  const hasText = text !== null && text.trim() !== "";
  const context = !hasText
    ? "No text, so no topic"
    : topic === TOPIC_UNKNOWN
      ? "Topic not available right now · original language"
    : topic === undefined
      ? topicCount === null
        ? "Not grouped into topics yet · original language"
        : "Published after the latest topic run · original language"
      : topic === null
        ? `Unclustered: fits none of the ${topicCount ? `${topicCount} ` : ""}topics · original language`
        : `Topic: ${topic} · original language`;
  return (
    <span className="flex min-w-0 flex-col gap-0.5">
      <span className={TYPE.label}>{context}</span>
      <span className={size === "body" ? `${TYPE.body} text-text-primary` : `${TYPE.cell} text-text-primary`}>
        {hasText ? text : "(no text)"}
      </span>
    </span>
  );
}

// Lỗi tải dữ liệu — câu cho người xem + nút thử lại (§9: error = message + retry; ux-reviewer N9). Chi tiết ở console
export function LoadError({ onRetry, what = "The data service is not reachable right now." }: { onRetry: () => void; what?: string }) {
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border-hairline bg-bg-card p-6">
      <p className={`m-0 ${TYPE.body}`}>{what}</p>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex min-h-[44px] cursor-pointer items-center rounded-full border border-border-hairline bg-bg-surface px-4 text-[13px] font-semibold text-text-primary hover:border-amber-600 hover:text-amber-700"
      >
        Try again
      </button>
    </div>
  );
}

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

// Số chính của một khối (ADR-0030, design-system §3b K): mỗi số có nhãn, 1 dòng nghĩa và link tới định nghĩa —
// không số trần. `share` = số này là một phần của số đứng trước (K4: thanh tỉ lệ + "N% of …")
export interface KeyNumber {
  value: string;
  label: string;
  note?: ReactNode;
  term?: string; // id mục trong "How every number on this page is computed" (anchor `term-<id>`)
  share?: { part: number; whole: number; of: string };
}

const LINK =
  "underline decoration-text-muted decoration-dotted decoration-1 underline-offset-[3px] hover:text-amber-700 hover:decoration-amber-600 hover:decoration-solid";

// Hộp Key numbers — component DUY NHẤT cho vai hộp số (K1). Số 28px căn trái trên dòng riêng → nhãn 15px w600 →
// ghi chú 13px (K2, tối đa 4 số); cao theo nội dung, dính khi ở cột phụ: `self-start` + `lg:sticky lg:top-6` (K3).
// `scope` = phạm vi hẹp hơn khối chứa (VD topic đang chọn), ghi ở dòng nhãn trên tiêu đề. `level`: 3 khi hộp nằm
// thẳng dưới tiêu đề khối h2 (tag h3, vai box-title), 4 khi nằm trong mục h3
export function KeyNumbers({ items, scope, level = 3 }: { items: KeyNumber[]; scope?: string; level?: 3 | 4 }) {
  const Heading = level === 3 ? "h3" : "h4";
  return (
    <div
      data-ux="key-numbers"
      className="flex flex-col gap-4 self-start rounded-xl border border-warm-border bg-warm-surface px-5 py-5 lg:sticky lg:top-6"
    >
      <div className="flex flex-col gap-1">
        {scope ? <span className={TYPE.eyebrow}>{scope.toUpperCase()}</span> : null}
        <Heading data-ux-role={level === 3 ? "box-title" : undefined} className={`m-0 ${TYPE.h4}`}>
          Key numbers
        </Heading>
      </div>
      <dl className="m-0 flex flex-col gap-4">
        {items.map((item) => {
          // Làm tròn XUỐNG trên số nguyên (nhân trước khi chia — .claude/rules/dashboard.md): 199 / 200 không được đọc
          // thành "100%" (code-reviewer); phần > 0 mà xuống 0 thì ghi "<1"
          const percent = item.share && item.share.whole > 0 ? Math.floor((item.share.part * 100) / item.share.whole) : null;
          const percentText = percent === 0 && item.share && item.share.part > 0 ? "<1" : `${percent}`;
          return (
            <div key={item.label} className="flex flex-col gap-1.5 border-t border-warm-border pt-4 first:border-t-0 first:pt-0">
              <dt className="flex flex-col gap-0.5">
                <span data-ux="kn-value" className={TYPE.metric}>
                  {item.value}
                </span>
                {item.term ? (
                  <a data-ux="kn-label" href={`#term-${item.term}`} className={`${TYPE.bodyStrong} ${LINK}`}>
                    {item.label}
                  </a>
                ) : (
                  <span data-ux="kn-label" className={TYPE.bodyStrong}>
                    {item.label}
                  </span>
                )}
              </dt>
              {percent !== null && item.share ? (
                <dd className="m-0 flex items-center gap-2.5">
                  <span aria-hidden="true" className="h-1 w-full max-w-[160px] overflow-hidden rounded-full bg-warm-border">
                    <span className="block h-full rounded-full bg-amber-600" style={{ width: `${percent}%` }} />
                  </span>
                  <span className={`${TYPE.note} whitespace-nowrap tabular-nums`}>
                    {percentText}% of {item.share.of}
                  </span>
                </dd>
              ) : null}
              {item.note ? <dd className={`m-0 ${TYPE.note}`}>{rich(item.note)}</dd> : null}
            </div>
          );
        })}
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

// Câu trả lời + ý chính bên trái, hộp Key numbers bên phải (dính khi cuộn). `below` (khối trải hết bề rộng) nằm
// NGOÀI lưới 2 cột: ô dính trượt trong cả lưới, nên khối nằm chung lưới sẽ bị hộp trượt đè lên (ADR-0030 K3)
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
  const hasNumbers = keyNumbers !== undefined && keyNumbers.length > 0;
  return (
    <div className="flex flex-col gap-6">
      {/* Không có Key numbers → câu trả lời trải hết bề rộng (L5: không chừa nửa phải trống) */}
      <div className={hasNumbers ? "grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]" : "flex flex-col"}>
        <div className="flex flex-col gap-5">
          <Answer>{answer}</Answer>
          {hasPoints ? (
            <div className="flex flex-col gap-2">
              {/* Hộp con nằm thẳng dưới tiêu đề khối h2: tag h3, vai box-title (T5 — không nhảy h2 → h4) */}
              <h3 data-ux-role="box-title" className={`m-0 ${TYPE.h4}`}>
                {pointsTitle}
              </h3>
              <Bullets items={points} />
            </div>
          ) : null}
          {extra}
        </div>
        {keyNumbers && keyNumbers.length > 0 ? <KeyNumbers items={keyNumbers} /> : null}
      </div>
      {below}
    </div>
  );
}

// Link tới định nghĩa trong phần "How every number on this page is computed"
// `tall`: vùng chạm cao 24px khi link đứng sát link khác (VD 2 link xếp chồng trong header bảng — WCAG 2.5.8)
export function TermLink({ term, children, tall = false }: { term: string; children: ReactNode; tall?: boolean }) {
  return (
    <a href={`#term-${term}`} className={`text-inherit ${LINK} ${tall ? "inline-flex min-h-[24px] items-center" : ""}`}>
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
