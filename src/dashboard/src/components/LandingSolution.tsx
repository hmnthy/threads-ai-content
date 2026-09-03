import { ChartLineUp, Graph, Sparkle } from "@phosphor-icons/react/dist/ssr";

const LAYERS = [
  {
    Icon: ChartLineUp,
    name: "Statistics layer",
    status: "live" as const,
    body: "Six intrinsic indices kept separate — popularity, engagement, virality, conversation, velocity, longevity — never blended into one score. Median and mean reported together, IQR and sample-size flags on every bucket, Mann-Whitney U + Cliff's delta for any group comparison, per-channel percentile-relative virality instead of an arbitrary threshold.",
  },
  {
    Icon: Graph,
    name: "NLP layer",
    status: "live" as const,
    body: "Multilingual sentence embeddings (content mixes Vietnamese, French and English naturally) feed UMAP + HDBSCAN for unsupervised topic discovery — see the Topic Explorer. A Code-Mixing Index, not a boolean flag, measures how much a post actually switches languages.",
  },
  {
    Icon: Sparkle,
    name: "Generative AI + RAG",
    status: "coming soon" as const,
    body: "Claude already labels discovered topic clusters in English. The next layer drafts new post ideas grounded — via retrieval over this channel's own highest-performing content — in the author's real voice, not a generic AI one.",
  },
];

export function LandingSolution() {
  return (
    <section id="solution" className="flex scroll-mt-20 flex-col gap-6 py-14">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">
          How it&apos;s solved
        </h2>
        <p className="max-w-2xl text-text-secondary">
          Three layers, built and verified in that order — each one grounded in cited methodology,
          not intuition.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {LAYERS.map(({ Icon, name, status, body }) => (
          <div
            key={name}
            className={`flex flex-col gap-3 rounded-xl border border-border-hairline p-6 ${
              status === "live" ? "bg-bg-card" : "bg-bg-sunken"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div
                className={`flex h-9 w-9 items-center justify-center rounded-full ${
                  status === "live" ? "bg-amber-soft text-amber-600" : "bg-bg-surface text-text-muted"
                }`}
              >
                <Icon size={18} aria-hidden="true" />
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                  status === "live" ? "bg-amber-soft text-amber-600" : "bg-bg-surface text-text-secondary"
                }`}
              >
                {status}
              </span>
            </div>
            <h3
              className={`text-[15px] font-semibold ${
                status === "live" ? "text-text-primary" : "text-text-muted"
              }`}
            >
              {name}
            </h3>
            <p className="text-sm leading-relaxed text-text-secondary">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
