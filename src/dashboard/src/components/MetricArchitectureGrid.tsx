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
  { name: "Popularity", formula: "views", status: "live", note: "Raw views — how many times the post was seen. Every rate below divides by it." },
  {
    name: "Engagement",
    formula: "(likes + replies + reposts + quotes) / views × 100",
    status: "live",
    note: "Share of views that led to any reaction. The denominator is views, not followers: interactions per view of the post.",
  },
  {
    name: "Share rate",
    formula: "(reposts + quotes) / views × 100",
    status: "live",
    note: "Reposts and quotes only. Threads exposes no separate shares field, so none is invented.",
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
    note: "Snapshots are scheduled every 4 hours since Aug 31, 2026, but only run while the collecting laptop is awake, so the series has long overnight gaps. The velocity view is not built yet.",
  },
  {
    name: "Longevity",
    formula: "(interactions at 72h − at 24h) / interactions at 72h",
    status: "deferred",
    note: "Formula specified, not implemented yet. It needs snapshots at 24 h and 72 h after posting."
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
