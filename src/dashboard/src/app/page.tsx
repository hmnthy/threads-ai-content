import { AnalyticsOverview } from "@/components/AnalyticsOverview";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-bg-border px-6 py-5">
        <h1 className="text-[24px] font-semibold tracking-tight text-text-primary">Overview</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Top posts and posting-time engagement, computed from verified live data (no NLP pipeline
          required).
        </p>
      </header>
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-6">
        <AnalyticsOverview />
      </main>
    </div>
  );
}
