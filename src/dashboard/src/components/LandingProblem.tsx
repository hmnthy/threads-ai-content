import { ChartBar, MagnifyingGlass, Warning } from "@phosphor-icons/react/dist/ssr";

const POINTS = [
  {
    Icon: ChartBar,
    title: "No real analytics depth",
    body: "Threads' own Insights expose views, likes, replies, reposts and quotes — no impressions, no reach, no shares, no timezone breakdown. Creators are left estimating.",
  },
  {
    Icon: MagnifyingGlass,
    title: "No topic-level insight",
    body: "Every post is judged in isolation. There's no built-in way to see which subjects, told which way, actually perform better across a channel's real history.",
  },
  {
    Icon: Warning,
    title: "No statistically honest reporting",
    body: "A single viral post drags a mean far above what a typical post looks like, and a 2-post \"best hour\" bucket gets reported with the same confidence as a 50-post one.",
  },
];

export function LandingProblem() {
  return (
    <section className="flex flex-col gap-6 py-14">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">The problem</h2>
        <p className="max-w-2xl text-text-secondary">
          Threads gives creators just enough data to make confident-sounding, unfounded decisions.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {POINTS.map(({ Icon, title, body }) => (
          <div
            key={title}
            className="flex flex-col gap-3 rounded-xl border border-border-hairline bg-bg-card p-6"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-soft text-amber-600">
              <Icon size={18} aria-hidden="true" />
            </div>
            <h3 className="text-[15px] font-semibold text-text-primary">{title}</h3>
            <p className="text-sm leading-relaxed text-text-secondary">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
