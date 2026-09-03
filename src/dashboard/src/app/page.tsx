import Link from "next/link";
import { LandingNav } from "@/components/LandingNav";
import { LandingHero } from "@/components/LandingHero";
import { LandingProblem } from "@/components/LandingProblem";
import { LandingSolution } from "@/components/LandingSolution";
import { LandingTechStack } from "@/components/LandingTechStack";
import { LandingComingSoon } from "@/components/LandingComingSoon";
import { LandingAuthor } from "@/components/LandingAuthor";

// Landing / story page (Tầng B, scoped — xem docs/claude/design-system.md §7 và
// plan phiên 2026-09-03). Trang duy nhất KHÔNG dùng Nav.tsx (tab pill) — có
// LandingNav riêng, chỉ 1 CTA vào /overview.
export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col">
      <LandingNav />
      <div className="mx-auto w-full max-w-[1280px] px-6">
        <LandingHero />
        <LandingProblem />
        <LandingSolution />
        <LandingTechStack />
        <LandingComingSoon />
        <LandingAuthor />
      </div>
      <footer className="border-t border-border-hairline py-6">
        <div className="mx-auto flex w-full max-w-[1280px] flex-wrap items-center justify-between gap-3 px-6 text-xs text-text-muted">
          <span>Personal project · All rights reserved</span>
          <Link href="/overview" className="font-medium text-amber-600 hover:text-amber-700">
            View live dashboard →
          </Link>
        </div>
      </footer>
    </div>
  );
}
