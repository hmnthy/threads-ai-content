import type { ReactNode } from "react";

// Mảnh dùng chung của landing (tầng B, docs/design/landing-handoff.md §2).

export type RoadmapStatus = "live" | "next" | "research";

// Pill lộ trình chỉ có live / next / research (UI-0001-status-labels); "preview" chỉ là câu mô tả
export function StatusPill({ status, label }: { status: RoadmapStatus; label?: string }) {
  const tone =
    status === "live"
      ? "bg-amber-soft text-amber-700"
      : "border border-border-hairline bg-bg-surface text-text-secondary";
  return (
    <span
      className={`whitespace-nowrap rounded-full px-2.5 py-[3px] text-[11px] font-medium ${tone}`}
    >
      {label ?? status}
    </span>
  );
}

export function SectionHead({
  eyebrow,
  title,
  children,
  onDark = false,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
  onDark?: boolean;
}) {
  return (
    <div className="flex max-w-[780px] flex-col gap-4">
      <span
        className={`font-mono text-[13px] font-medium ${onDark ? "text-amber-on-dark" : "text-amber-600"}`}
      >
        {eyebrow}
      </span>
      <h2 className="m-0 text-[clamp(32px,3.6vw,46px)] font-extrabold leading-[1.08] tracking-[-0.035em] [text-wrap:balance]">
        {title}
      </h2>
      {children ? (
        <p
          className={`m-0 text-base leading-[1.65] [text-wrap:pretty] ${onDark ? "text-dark-text-secondary" : "text-text-secondary"}`}
        >
          {children}
        </p>
      ) : null}
    </div>
  );
}

// Nút "Method and limits" — cao 44px (vùng chạm), mở khối phương pháp ngay tại chỗ, không modal
export function MethodButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="h-11 cursor-pointer border-0 bg-transparent px-1 text-[13px] font-medium text-amber-600 hover:text-amber-700"
    >
      {open ? "Hide method and limits" : "Method and limits"}
    </button>
  );
}

export function MethodBlock({ formula, limits }: { formula: ReactNode; limits: ReactNode }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-5 rounded-xl bg-bg-sunken px-5 py-4">
      <span className="font-mono text-[12.5px] leading-[1.7] text-text-secondary">{formula}</span>
      <span className="text-[13px] leading-[1.6] text-text-secondary">{limits}</span>
    </div>
  );
}

export const SECTION = "mx-auto box-border w-full max-w-[1200px] scroll-mt-[72px] px-4 sm:px-8";

export const PANEL =
  "flex flex-col rounded-[20px] border border-border-hairline bg-bg-card px-5 pb-5 pt-7 sm:px-8";
