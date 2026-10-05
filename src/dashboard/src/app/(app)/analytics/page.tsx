import { AnalyticsBreakdown } from "@/components/AnalyticsBreakdown";

export default function AnalyticsPage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-border-hairline px-6 py-5">
        <h1 className="text-[24px] font-semibold tracking-tight text-text-primary">Analytics</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Which posts stand out on each index, and how engagement varies with posting time — every
          aggregate shown with the number of posts behind it.
        </p>
      </header>
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-6">
        <AnalyticsBreakdown />
      </main>
    </div>
  );
}
