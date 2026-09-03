interface IndexCard {
  name: string;
  formula: string;
  status: "live" | "deferred";
  note: string;
}

// Copy khớp nguyên văn docs/claude/data-model.md "Metric Architecture" — 6 index
// tách riêng, không blend thành 1 điểm số. Nội dung tĩnh, không phụ thuộc cửa sổ
// thời gian đang chọn.
const INDICES: IndexCard[] = [
  { name: "Popularity", formula: "views", status: "live", note: "Raw reach. Kept unnormalised so it can anchor the other five." },
  {
    name: "Engagement",
    formula: "(likes + replies + reposts + quotes) / views × 100",
    status: "live",
    note: "Quotes were missing from the original formula until the 2026-08-30 fix.",
  },
  {
    name: "Virality",
    formula: "(reposts + quotes) / views × 100",
    status: "live",
    note: "Redistribution only. Threads exposes no shares field, so none is invented.",
  },
  {
    name: "Conversation",
    formula: "replies / views × 100",
    status: "live",
    note: "Total replies — the only reply count post-level insights return.",
  },
  {
    name: "View velocity",
    formula: "Δviews / Δt",
    status: "deferred",
    note: "Needs two snapshots per post. The 4-hour job has not run long enough yet.",
  },
  {
    name: "Longevity",
    formula: "not implemented",
    status: "deferred",
    note: "Waiting on a longer snapshot history before a formula is committed.",
  },
];

export function MetricArchitectureGrid() {
  return (
    <section className="flex flex-col gap-3 pt-10">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h2 className="text-xl font-bold tracking-tight text-text-primary">Metric architecture</h2>
        <span className="text-[13px] text-text-secondary">
          Six indices kept separate. Nothing is blended into a single score.
        </span>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {INDICES.map((index) => (
          <div
            key={index.name}
            className={`flex flex-col gap-2.5 rounded-xl border border-border-hairline p-5 ${
              index.status === "live" ? "bg-bg-card" : "bg-bg-sunken"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <span
                className={`text-[15px] font-semibold ${
                  index.status === "live" ? "text-text-primary" : "text-text-muted"
                }`}
              >
                {index.name}
              </span>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                  index.status === "live" ? "bg-amber-soft text-amber-600" : "bg-bg-surface text-text-secondary"
                }`}
              >
                {index.status}
              </span>
            </div>
            <span className="font-mono text-[12.5px] leading-relaxed break-words text-text-secondary">
              {index.formula}
            </span>
            <span className="text-[13px] leading-snug text-text-muted">{index.note}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
