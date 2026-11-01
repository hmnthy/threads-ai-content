import type { ReactNode } from "react";
import { TYPE } from "@/lib/typeScale";

// Mảnh dùng chung của landing (tầng B, docs/design/landing-handoff.md §2). Panel, câu trả lời, Method and limits của
// landing dùng chính component của trang app (`AppBlock.tsx` + `LandingBlocks`, ADR-0032) — ở đây chỉ còn phần riêng
// tầng B: đầu section display-2 (X1) và pill lộ trình.

export type RoadmapStatus = "live" | "next" | "research";

// Pill lộ trình chỉ có live / next / research (UI-0001-status-labels); "preview" chỉ là câu mô tả. Chữ vai label 12px
export function StatusPill({ status, label }: { status: RoadmapStatus; label?: string }) {
  const tone =
    status === "live"
      ? "bg-amber-soft text-amber-700"
      : "border border-border-hairline bg-bg-surface text-text-secondary";
  return (
    <span className={`whitespace-nowrap rounded-full px-2.5 py-[3px] text-[12px] font-semibold ${tone}`}>
      {label ?? status}
    </span>
  );
}

// Đầu section landing: eyebrow số mono 12.5 amber ("01 · Problem") → h2 display-2 → câu dẫn vai lead 18px (§3)
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
    // Chữ chạy hết bề rộng khung (L5) — không giới hạn 780px như bản cũ (ux-reviewer PR 2b)
    <div className="flex flex-col gap-4">
      <span className={`${TYPE.eyebrowNum} ${onDark ? "text-amber-on-dark" : "text-amber-600"}`}>{eyebrow}</span>
      <h2 className="m-0 text-[clamp(32px,3.6vw,46px)] font-extrabold leading-[1.08] tracking-[-0.035em] [text-wrap:balance]">
        {title}
      </h2>
      {children ? (
        <p
          className={`m-0 text-[18px] leading-[1.6] [text-wrap:pretty] ${onDark ? "text-dark-text-secondary" : "text-text-secondary"}`}
        >
          {children}
        </p>
      ) : null}
    </div>
  );
}

// Lưới 3 cột của landing từ 1024px: Q1–Q3 (Problem) thẳng cột với 3 tầng Measure / Group / Search (Approach) ngay dưới
// — 3 cột bằng nhau cách 96px (chỗ mũi tên nối giữa 2 tầng)
export const LAYER_GRID = "lg:grid-cols-3 lg:gap-x-24";

export const SECTION = "mx-auto box-border w-full max-w-[1200px] scroll-mt-[72px] px-4 sm:px-8";
