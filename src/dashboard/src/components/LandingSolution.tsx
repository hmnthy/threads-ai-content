import type { ReactNode } from "react";
import { SECTION, SectionHead, StatusPill, type RoadmapStatus } from "@/components/LandingParts";
import { axisPct, count, pct, rankAmongOthers, rowSwarm, type LandingData } from "@/lib/landing";

// "How it solves" (handoff §3.3): 3 tầng sản phẩm — thống kê, NLP, knowledge base — theo 1 bài
// thật. Trạng thái theo code đang chạy, không theo roadmap (UI-L20260903-stack-real-status).
// Knowledge base là `next`, không ô hỏi đáp trước cổng Phase F (UI-0001-kb-next).

function Layer({
  num,
  title,
  status,
  body,
  slotLabel,
  children,
}: {
  num: string;
  title: string;
  status: RoadmapStatus;
  body: string;
  slotLabel: string;
  children: ReactNode;
}) {
  const live = status === "live";
  return (
    <div
      className={`flex flex-col gap-3.5 rounded-2xl p-6 ${
        live
          ? "border border-t-[3px] border-border-hairline border-t-amber-on-dark bg-bg-card"
          : "border border-dashed border-chart-dot-faint bg-bg-sunken"
      }`}
    >
      <div className="flex items-baseline justify-between">
        <span
          className={`font-mono text-[28px] font-semibold tracking-[-0.02em] ${live ? "text-text-primary" : "text-text-muted"}`}
        >
          {num}
        </span>
        <StatusPill status={status} />
      </div>
      <span
        className={`text-xl font-bold tracking-[-0.02em] ${live ? "" : "text-text-secondary"}`}
      >
        {title}
      </span>
      <span className="text-sm leading-[1.55] text-text-secondary">{body}</span>
      <div
        className={`mt-auto flex flex-col gap-2.5 rounded-xl px-4 py-3.5 ${live ? "bg-bg-sunken" : "bg-bg-card"}`}
      >
        <span className="text-[11px] font-semibold text-text-muted">{slotLabel}</span>
        {children}
      </div>
    </div>
  );
}

function Connector({ arrow, label, live }: { arrow: string; label: string; live: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-1">
      <span
        aria-hidden="true"
        className={`text-xl leading-none ${live ? "text-amber-600" : "text-text-muted"}`}
      >
        {arrow}
      </span>
      <span className="text-center text-[11px] leading-[1.35] text-text-secondary">{label}</span>
    </div>
  );
}

const GRID = "grid grid-cols-[minmax(0,1fr)_64px_minmax(0,1fr)_64px_minmax(0,1fr)]";

export function LandingSolution({ data }: { data: LandingData | null }) {
  const hero = data?.hero ?? null;
  const heroTopic = hero ? (data!.topics.find((t) => t.id === hero.topicId) ?? null) : null;
  const channel = data?.channel ?? null;
  const rank = hero && channel ? rankAmongOthers(channel.rates, hero.rate) : null;
  const answers =
    data && data.summary.reply_roles.author_answer > 0
      ? count(data.summary.reply_roles.author_answer)
      : null;

  return (
    <section
      id="approach"
      data-screen-label="03 How it solves"
      className={`${SECTION} flex flex-col gap-10 border-t border-rule py-[104px]`}
    >
      <SectionHead eyebrow="02 · Approach" title="Three layers, one per question, built on the same data.">
        Follow the post above through all three. Layer 2&apos;s topics become layer 1&apos;s comparison
        groups, and each post&apos;s text, tagged with its topic, becomes what layer 3 searches.
      </SectionHead>

      <div className="-mx-2 overflow-x-auto px-2">
        <div className="flex min-w-[980px] flex-col">
          <div className="flex items-center gap-4 rounded-2xl bg-dark-bg px-[22px] py-4 text-dark-text">
            <span className="whitespace-nowrap font-mono text-xs font-medium text-amber-on-dark">
              input
            </span>
            <span className="min-w-0 flex-1 text-[15px] leading-[1.5]">
              {hero ? `"${hero.firstLine}"` : "One post, rebuilt with its own continuations."}
            </span>
            <span className="whitespace-nowrap font-mono text-xs text-dark-text-muted">
              the post plus the author&apos;s follow-up parts, rebuilt from reply links
            </span>
          </div>
          <div className={`${GRID} h-9`} aria-hidden="true">
            <div className="flex justify-center">
              <div className="w-0.5 bg-amber-on-dark" />
            </div>
            <span />
            <div className="flex justify-center">
              <div className="w-0.5 bg-amber-on-dark" />
            </div>
            <span />
            <div className="flex justify-center">
              <div className="w-0.5 bg-rule" />
            </div>
          </div>
          <div className={`${GRID} items-stretch`}>
            <Layer
              num="01"
              title="Measure"
              status="live"
              body="Answers Q1. Each post's engagement rate is placed among all the channel's posts, with the median, the middle half and the post count shown. Each topic is then compared with the rest of the channel, with an effect size and a corrected p-value."
              slotLabel="This post"
            >
              {hero && channel ? (
                <>
                  <div className="relative h-[30px]" aria-hidden="true">
                    <div className="absolute inset-x-0 top-[15px] h-px bg-rule" />
                    {rowSwarm(channel.rates, data!.axisMax, 15, 3.4, 4.2, 300).map((dot, i) => (
                      <div
                        key={i}
                        className="absolute h-1 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-chart-dot"
                        style={dot}
                      />
                    ))}
                    <div
                      className="absolute bottom-0.5 top-0.5 w-0.5 bg-text-primary"
                      style={{ left: axisPct(channel.stats.median, data!.axisMax) }}
                    />
                    <div
                      className="absolute top-[15px] h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-amber-600"
                      style={{ left: axisPct(hero.rate, data!.axisMax) }}
                    />
                  </div>
                  <span className="text-[15px] font-semibold leading-[1.4] tabular-nums">
                    <span className="text-amber-600">{pct(hero.rate)}</span>
                    {rank && rank.others > 0
                      ? ` · higher than ${rank.below} of the other ${count(rank.others)}`
                      : ""}
                    {channel.stats.n > 0 ? ` · channel median ${pct(channel.stats.median)}` : ""}
                  </span>
                </>
              ) : (
                <span className="text-[13px] text-text-secondary">No live data right now.</span>
              )}
            </Layer>
            <Connector arrow="←" label="topic becomes the comparison group" live />
            <Layer
              num="02"
              title="Group"
              status="live"
              body="Answers Q2. Posts are embedded and clustered by meaning, across Vietnamese, French and English. A language model only names the clusters."
              slotLabel="This post"
            >
              {hero && heroTopic ? (
                <>
                  <div className="relative h-[30px]" aria-hidden="true">
                    {data!.mapPoints.map((p, i) => {
                      const own = p.topicId === heroTopic.id;
                      return (
                        <div
                          key={i}
                          className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full ${
                            own ? "bg-amber-600" : p.topicId === null ? "bg-rule" : "bg-chart-dot-faint"
                          }`}
                          style={{
                            left: `${2 + p.x * 0.96}%`,
                            top: 2 + (100 - p.y) * 0.26,
                            width: own ? 5 : 3,
                            height: own ? 5 : 3,
                          }}
                        />
                      );
                    })}
                  </div>
                  <span className="text-[15px] font-semibold leading-[1.4] tabular-nums">
                    <span className="text-amber-600">{heroTopic.name}</span> · named by Claude ·{" "}
                    {hero.nearestToCentre ? "nearest post to the centre, similarity" : "similarity to the centre"}{" "}
                    {hero.similarity?.toFixed(3) ?? "—"}
                  </span>
                </>
              ) : (
                <span className="text-[13px] text-text-secondary">
                  {hero ? "This post fits no cluster in the latest run." : "No live data right now."}
                </span>
              )}
            </Layer>
            <Connector arrow="→" label="text and topic become documents" live={false} />
            <Layer
              num="03"
              title="Search"
              status="next"
              body="Answers Q3. Posts and the author's answers become one knowledge base, searched by keyword and by meaning. It will be scored on a test set of real questions once a privacy decision is made."
              slotLabel="This post, once built"
            >
              <span className="font-mono text-[12.5px] leading-[1.6] text-text-secondary">
                document · full_text{heroTopic ? ` · ${heroTopic.id}` : ""}
                <br />
                {answers ? `indexed with ${answers} author answers` : "indexed with the author's answers"}
              </span>
            </Layer>
          </div>
        </div>
      </div>
      <span className="max-w-[780px] text-[13.5px] leading-[1.6] text-text-secondary">
        A chatbot and a brand site for the channel come after the knowledge base passes its
        retrieval benchmark, not before.
      </span>
    </section>
  );
}
