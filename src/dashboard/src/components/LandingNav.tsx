import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

// Navbar riêng cho landing (Tầng B) — không có tab pill, chỉ logo + 1 CTA vào
// tool thật. Khác Nav.tsx (Tầng A) vốn có topbar + tab pill 3 trang.
export function LandingNav() {
  return (
    <div className="border-b border-border-hairline">
      <div className="mx-auto flex w-full max-w-[1280px] items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-600 text-white">
            <span className="text-sm font-semibold leading-none">@</span>
          </div>
          <span className="text-sm font-semibold tracking-tight text-text-primary">
            Threads AI Content
          </span>
        </div>
        <Link
          href="/overview"
          className="flex h-9 items-center gap-1.5 rounded-full bg-amber-600 px-4 text-[13px] font-semibold text-white transition-colors hover:bg-amber-700"
        >
          View live dashboard
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
