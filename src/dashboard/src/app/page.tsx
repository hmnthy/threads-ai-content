import { BrandLogo } from "@/components/BrandLogo";
import { LandingAuthor } from "@/components/LandingAuthor";
import { LandingCta } from "@/components/LandingCta";
import { LandingHero } from "@/components/LandingHero";
import { LandingNav } from "@/components/LandingNav";
import { LandingProblem } from "@/components/LandingProblem";
import { LandingProof } from "@/components/LandingProof";
import { LandingSolution } from "@/components/LandingSolution";
import { LandingTechStack } from "@/components/LandingTechStack";
import { getAnalyticsOverview, getContentUnits, getPipelineSummary, getTopics } from "@/lib/api";
import { buildLandingData, dayMonthYear, type LandingData } from "@/lib/landing";

// Landing / story page (Tầng B — docs/design/landing-handoff.md, design-system §7). Trang duy
// nhất KHÔNG dùng Nav.tsx (tab pill): có LandingNav riêng, mọi CTA vào /overview.
// Server component: lấy số thật từ API mỗi request; API lỗi → mỗi khối hiện trạng thái rỗng
// rõ ràng thay vì khung trục trống (design-system §9).
async function loadLandingData(): Promise<LandingData | null> {
  try {
    const [units, topics, overview, summary] = await Promise.all([
      getContentUnits(),
      getTopics(),
      getAnalyticsOverview(),
      getPipelineSummary(),
    ]);
    return buildLandingData(units, topics, overview, summary);
  } catch (error) {
    // in ra log server để lỗi lập trình không bị nhầm thành "API không chạy"
    console.error("landing: could not load data", error);
    return null;
  }
}

export default async function LandingPage() {
  const data = await loadLandingData();
  return (
    <div className="landing flex flex-1 flex-col">
      <LandingNav />
      <main id="top" className="flex flex-col">
        <LandingHero data={data} />
        <LandingProblem data={data} />
        <LandingSolution data={data} />
        <LandingProof data={data} />
        <LandingTechStack data={data} />
        <LandingAuthor data={data} />
        <LandingCta />
      </main>
      <footer className="border-t border-rule bg-bg-card">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-6 px-4 py-7 sm:px-8">
          <div className="flex flex-wrap items-center gap-4">
            <BrandLogo variant="lockup" height={24} />
            <span className="text-[13px] text-text-secondary">The algorithm, read back to you.</span>
          </div>
          <div className="flex flex-col gap-1 sm:items-end sm:text-right">
            {/* Câu miễn trừ nguyên văn (ADR-0009) — tests/test_branding.py chặn khi mất */}
            <span className="text-[12.5px] text-text-secondary">
              Not affiliated with Meta. Threads is a trademark of Meta Platforms, Inc.
            </span>
            {data?.summary.latest_snapshot_at ? (
              <span className="font-mono text-xs text-text-muted">
                Data as of {dayMonthYear(data.summary.latest_snapshot_at)}
              </span>
            ) : null}
          </div>
        </div>
      </footer>
    </div>
  );
}
