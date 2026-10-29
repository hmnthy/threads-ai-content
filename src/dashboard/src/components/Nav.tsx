"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChartLineUp, ChartPieSlice, CaretDown, Compass } from "@phosphor-icons/react/dist/ssr";
import { BrandLogo } from "@/components/BrandLogo";

// Topbar + tab pill — docs/claude/design-system.md §7 Tầng A: topbar (logo +
// tagline + account pill + avatar) rồi tab pill ngay dưới, không sidebar.
const TABS = [
  { href: "/overview", label: "Overview", Icon: ChartPieSlice },
  { href: "/analytics", label: "Analytics", Icon: ChartLineUp },
  { href: "/topics", label: "Topic Explorer", Icon: Compass },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <div className="border-b border-border-hairline">
      <div className="mx-auto flex w-full max-w-[1280px] flex-wrap items-center justify-between gap-4 px-6 py-4">
        <Link href="/" className="flex items-center gap-4 leading-tight">
          {/* Lockup đã chứa chữ "Unthreaded"; tagline giữ dạng chữ HTML (ADR-0021). Topbar 36px + tagline 15px
              cạnh logo, ngăn bằng vạch dọc, ẩn tagline dưới 640px; hoạt cảnh phát lại mỗi 15 giây (ADR-0026) */}
          <BrandLogo variant="lockup-replay" height={36} />
          <span aria-hidden="true" className="hidden h-7 w-px bg-border-hairline sm:block" />
          <span className="hidden text-[15px] font-medium text-text-secondary sm:inline">The algorithm, read back to you.</span>
        </Link>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            className="flex h-9 items-center gap-2 rounded-full border border-border-hairline bg-bg-surface px-3.5 text-[13px] font-medium text-text-primary"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-positive" aria-hidden="true" />
            <span>thydilammuon</span>
            <CaretDown size={13} className="text-text-secondary" aria-hidden="true" />
          </button>
          <div className="h-8 w-8 overflow-hidden rounded-full border border-border-hairline bg-bg-surface">
            <Image
              src="/photo-author.jpg"
              alt="Channel author"
              width={32}
              height={32}
              className="h-full w-full object-cover"
              style={{ transform: "scale(1.75)", transformOrigin: "50% 34%" }}
            />
          </div>
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-[1280px] flex-wrap items-center gap-1 px-6 pb-3">
        {TABS.map(({ href, label, Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex min-h-[44px] flex-none items-center gap-2 rounded-full px-3 text-[15px] transition-colors sm:px-4 ${
                active
                  ? "bg-bg-surface font-semibold text-text-primary"
                  : "font-medium text-text-secondary hover:bg-bg-surface hover:text-text-primary"
              }`}
            >
              <Icon size={18} aria-hidden="true" />
              {label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
