import type { ReactNode } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp } from "@phosphor-icons/react/dist/ssr";
import { TYPE } from "@/lib/typeScale";
import { SECTION, SectionHead, StatusPill, type RoadmapStatus } from "@/components/LandingParts";
import { axisPct, count, HERO_ENGLISH, pct, rankAmongOthers, rowSwarm, type LandingData } from "@/lib/landing";

// "How it solves" (handoff §3.3): 3 tầng sản phẩm — thống kê, NLP, knowledge base — theo 1 content unit thật. Trạng
// thái theo code đang chạy, không theo roadmap (UI-L20260903-stack-real-status). Knowledge base là `next`, không ô hỏi
// đáp trước cổng Phase F (UI-0001-kb-next; trang demo `/rag-pipeline` chỉ xếp hạng đoạn nguồn, không phải knowledge base
// — ADR-0037). Thy 2026-11-01 (ADR-0032): tên tầng là tiêu đề khối thật (h3 26px), 3 tầng
// cùng lưới với Q1–Q3 của "Problem"; dưới 1024px xếp dọc (không cuộn ngang), mũi tên đổi hướng theo bố cục.

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
          ? "border border-t-[3px] border-border-hairline border-t-amber-600 bg-bg-card"
          : "border border-dashed border-chart-dot-faint bg-bg-sunken"
      }`}
    >
      <div className="flex items-baseline justify-between">
        <span className={`${TYPE.eyebrowNum} ${live ? "text-amber-600" : "text-text-muted"}`}>{num}</span>
        <StatusPill status={status} />
      </div>
      {/* Cùng màu với mọi tiêu đề khối (T3); "chưa làm" thấy qua pill trạng thái + viền đứt nét */}
      <h3 className={`m-0 ${TYPE.h2}`}>{title}</h3>
      <p className={`m-0 ${TYPE.body}`}>{body}</p>
      <div
        className={`mt-auto flex flex-col gap-2.5 rounded-xl px-4 py-3.5 ${live ? "bg-bg-sunken" : "bg-bg-card"}`}
      >
        <span className={`${TYPE.label} font-semibold`}>{slotLabel}</span>
        {children}
      </div>
    </div>
  );
}

// Mũi tên nối 2 tầng: ngang từ 1024px (lưới 3 cột), dọc khi các tầng xếp chồng
function Connector({ to, label, live }: { to: "left" | "right"; label: string; live: boolean }) {
  const tone = live ? "text-amber-600" : "text-text-muted";
  const Wide = to === "left" ? ArrowLeft : ArrowRight;
  const Narrow = to === "left" ? ArrowUp : ArrowDown;
  return (
    <div className="flex items-center justify-center gap-2 py-2 lg:flex-col lg:px-1 lg:py-0">
      <Wide aria-hidden="true" size={22} className={`hidden lg:block ${tone}`} />
      <Narrow aria-hidden="true" size={22} className={`lg:hidden ${tone}`} />
      <span className={`text-center ${TYPE.label} text-text-secondary`}>{label}</span>
    </div>
  );
}

// Cột nối 96px: nhãn mũi tên 12px vừa trong cột (64px làm chữ "comparison" tràn); cùng khoảng cách với Q1–Q3
const GRID = "grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_96px_minmax(0,1fr)_96px_minmax(0,1fr)]";

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
        Follow the content unit above through all three layers. Topics from Group become the comparison groups in
        Measure; Search will index each content unit&apos;s text together with its topic.
      </SectionHead>

      <div className="flex flex-col">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1.5 rounded-2xl bg-dark-bg px-[22px] py-4 text-dark-text">
          <span className={`whitespace-nowrap ${TYPE.mono} font-medium text-amber-on-dark`}>input</span>
          <span className="min-w-0 flex-1 text-[15px] leading-[1.5]">
            {hero ? (
              <>
                &ldquo;{hero.firstLine}&rdquo;{" "}
                <span className="text-dark-text-secondary">(original language · about: {HERO_ENGLISH})</span>
              </>
            ) : (
              "One content unit, rebuilt with its own follow-up parts."
            )}
          </span>
          <span className={`${TYPE.mono} text-dark-text-muted`}>
            the opening post plus the author&apos;s follow-up parts, joined through the reply chain
          </span>
        </div>
        <div className={`${GRID} hidden h-9 lg:grid`} aria-hidden="true">
          <div className="flex justify-center">
            <div className="w-0.5 bg-amber-600" />
          </div>
          <span />
          <div className="flex justify-center">
            <div className="w-0.5 bg-amber-600" />
          </div>
          <span />
          <div className="flex justify-center">
            <div className="w-0.5 bg-rule" />
          </div>
        </div>
        <div className={`${GRID} mt-6 items-stretch lg:mt-0`}>
          <Layer
            num="01"
            title="Measure"
            status="live"
            body="Answers Q1. Each content unit's engagement rate is ranked against the channel's other content units, next to the median, the middle half and how many content units they rest on. Each topic is then tested against the rest of the channel (see Proof)."
            slotLabel="This content unit"
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
                <span className={`${TYPE.body} tabular-nums`}>
                  <strong className="font-semibold text-amber-700">{pct(hero.rate)}</strong>
                  {rank && rank.others > 0 ? ` · higher than ${rank.below} of the other ${count(rank.others)}` : ""}
                  {channel.stats.n > 0 ? ` · channel median ${pct(channel.stats.median)}` : ""}
                </span>
              </>
            ) : (
              <span className={TYPE.note}>No live data right now.</span>
            )}
          </Layer>
          <Connector to="left" label="topic becomes the comparison group" live />
          <Layer
            num="02"
            title="Group"
            status="live"
            body="Answers Q2. Each content unit's text becomes an embedding, a vector of its meaning that works across Vietnamese, French and English. Content units with nearby vectors are grouped into topics. Claude only names the topics; it does not form them."
            slotLabel="This content unit"
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
                <span className={`${TYPE.body} tabular-nums`}>
                  Topic <strong className="font-semibold text-amber-700">{heroTopic.name}</strong> (named by Claude) ·{" "}
                  {hero.nearestToCentre ? "the most typical content unit of its topic, similarity" : "similarity to the topic's centre"}{" "}
                  {hero.similarity?.toFixed(3) ?? "—"}
                </span>
                <span className={TYPE.note}>
                  Similarity is the cosine between this content unit&apos;s embedding and its topic&apos;s average embedding: at
                  most 1, and higher means more typical of the topic.
                </span>
              </>
            ) : (
              <span className={TYPE.note}>
                {hero ? "This content unit fits no topic in the latest run." : "No live data right now."}
              </span>
            )}
          </Layer>
          <Connector to="right" label="text and topic go into the search index" live={false} />
          <Layer
            num="03"
            title="Search"
            status="next"
            body="Answers Q3. Content units and the answers to followers will become one knowledge base, searched by keyword and by meaning. It will be scored on a test set of real follower questions, once their privacy review is done."
            slotLabel="This content unit, once built"
          >
            <span className={`${TYPE.mono} text-text-secondary`}>
              document · full text{heroTopic ? ` · topic "${heroTopic.name}"` : ""}
              <br />
              {answers ? `indexed with ${answers} answers to followers` : "indexed with the answers to followers"}
            </span>
          </Layer>
        </div>
      </div>
      <p className={`m-0 ${TYPE.note}`}>
        A chatbot and a brand site for the channel come after the knowledge base passes its retrieval benchmark, not
        before.
      </p>
    </section>
  );
}
