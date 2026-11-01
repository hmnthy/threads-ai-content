"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { BrandLogo } from "@/components/BrandLogo";
import { Answer, LandingBlocks, MethodSection, rich, Section, ToggleGroup, TYPE } from "@/components/AppBlock";
import { formatIqrRange } from "@/components/DistributionCaption";
import { CONTENT_UNIT } from "@/lib/appSections";
import {
  HERO_QUESTION,
  axisPct,
  count,
  dayMonthYear,
  monthYear,
  partOfWhole,
  pct,
  rankAmongOthers,
  swarm,
  ticks,
  type LandingData,
} from "@/lib/landing";

const MIN_WIDTH = 720; // dưới mức này beeswarm cuộn ngang trong vùng cuộn có focus bàn phím (UI-L20260829-mobile)
const DESIGN_WIDTH = 1136; // bề rộng mockup: khoảng cách chấm 9px
const CENTRE_Y = 112;

// Bỏ đúng 1 lần giá trị của bài hero khỏi tập rồi thêm vào cuối: bài hero chiếm 1 chỗ trong
// swarm như mọi chấm khác nhưng được vẽ riêng
function withHeroLast(rates: number[], heroRate: number): number[] {
  const i = rates.indexOf(heroRate);
  return [...(i === -1 ? rates : [...rates.slice(0, i), ...rates.slice(i + 1)]), heroRate];
}

export function LandingHero({ data }: { data: LandingData | null }) {
  return (
    <section
      data-screen-label="01 Hero"
      className="mx-auto box-border flex w-full max-w-[1200px] flex-col px-4 pb-24 pt-14 sm:px-8"
    >
      <div className="flex flex-col items-center gap-6 text-center">
        {/* Hoạt cảnh chạy 1 lần mỗi 15 giây (Thy 2026-10-29); reduced-motion → bản tĩnh (BrandLogoReplay) */}
        <BrandLogo variant="lockup-replay" height={64} />
        <h1 className="m-0 text-[clamp(44px,6.4vw,76px)] font-extrabold leading-none tracking-[-0.04em] [text-wrap:balance]">
          The algorithm, read back to you.
        </h1>
        <p className="m-0 max-w-[640px] text-[18px] leading-[1.6] text-text-secondary [text-wrap:pretty]">
          Unthreaded shows how each content unit on a Threads channel did compared with the rest of that channel, not
          with Threads as a whole. Every figure says how many content units it rests on.
        </p>
        {/* Định nghĩa ngay sau lần đầu dùng từ (Thy 2026-11-01: người lạ không gặp từ trước khi biết nghĩa) */}
        <p className={`m-0 max-w-[720px] ${TYPE.note}`}>{rich(CONTENT_UNIT)}</p>
        <div className="flex flex-wrap justify-center gap-3">
          {/* Vai nút CTA 15px w600 của trang giới thiệu (Thy 2026-11-01, ADR-0032) */}
          <Link
            href="/overview"
            className={`flex h-12 items-center rounded-full bg-amber-600 px-[22px] ${TYPE.cta} text-white hover:bg-amber-700`}
          >
            View live dashboard
          </Link>
          <a
            href="#method"
            className={`flex h-12 items-center rounded-full border border-border-hairline bg-bg-card px-[22px] ${TYPE.cta} text-text-primary`}
          >
            See how it works
          </a>
        </div>
      </div>
      {data ? <ChannelStats data={data} /> : null}
      {/* Panel hero dùng khuôn khối chung (C1/C2) ở hình khối landing; tiêu đề khối nằm ngay dưới H1 — ngoại lệ T5
          Thy duyệt 2026-11-01 (ADR-0032), máy đo nhận qua data-ux="hero-panel" */}
      <div className="mt-10">
        <LandingBlocks>
          {data?.hero ? (
            <HeroPanel data={data} />
          ) : (
            <HeroEmpty reason={data === null ? "offline" : data.heroFound ? "no-views" : "missing"} />
          )}
        </LandingBlocks>
      </div>
    </section>
  );
}

// Dải thống kê kênh (Thy duyệt 2026-10-08): định nghĩa mẫu số MỘT lần trước bài mẫu, để các câu sau chỉ cần nói
// "the channel's content units" (một tên "content units" trên cả landing — Thy 2026-11-01). Mọi số từ API:
// /pipeline/summary, /analytics/overview.
function ChannelStats({ data }: { data: LandingData }) {
  const run = data.summary.latest_cluster_run;
  const total = data.summary.content_units;
  const measured = data.channel.stats.n;
  // Median luôn kèm IQR + n (N4/K5); số là phần của số trước ghi % làm tròn xuống (K4) — ux-reviewer PR 2b
  const items: { value: string; label: string; note?: string }[] = [
    {
      value: count(total),
      label: data.firstPostAt ? `content units since ${monthYear(data.firstPostAt)}` : "content units",
    },
    {
      value: count(measured),
      label: "with recorded views",
      note: total > 0 ? `${partOfWhole(measured, total)} of ${count(total)}` : undefined,
    },
    {
      value: measured > 0 ? pct(data.channel.stats.median) : "—",
      label: "median engagement rate",
      note: measured > 0 ? `middle half ${formatIqrRange(data.channel.stats)} (IQR) · n = ${count(measured)}` : undefined,
    },
    ...(run ? [{ value: String(run.n_clusters), label: "topics" }] : []),
  ];
  return (
    <div className="mt-12 flex flex-col items-center gap-3">
      <dl className="m-0 flex flex-wrap justify-center gap-x-10 gap-y-4">
        {items.map((item) => (
          <div key={item.label} className="flex flex-col items-center gap-0.5">
            <dt className={`order-2 ${TYPE.note}`}>{item.label}</dt>
            <dd className={`order-1 m-0 ${TYPE.metric}`}>{item.value}</dd>
            {item.note ? <dd className={`order-3 m-0 ${TYPE.mono} text-text-muted`}>{item.note}</dd> : null}
          </div>
        ))}
      </dl>
      {data.summary.latest_snapshot_at ? (
        <span className={`${TYPE.mono} text-text-muted`}>Data as of {dayMonthYear(data.summary.latest_snapshot_at)}</span>
      ) : null}
    </div>
  );
}

const EMPTY_REASON = {
  offline: "The data service is not reachable right now. Reload in a moment.",
  "no-views": "This content unit has no recorded views yet, so it cannot be placed against the channel.",
  missing: "This content unit is not in the database yet, so it cannot be placed against the channel.",
} as const;

const HERO_PURPOSE =
  "Ranks this content unit against the channel's other content units by engagement rate: likes, replies, reposts and quotes per 100 views of its opening post.";

function HeroEmpty({ reason }: { reason: keyof typeof EMPTY_REASON }) {
  return (
    <Section id="example" ux="hero-panel" n="00" short="One real content unit" title={HERO_QUESTION} purpose={HERO_PURPOSE}>
      <p className={`m-0 ${TYPE.body}`}>{EMPTY_REASON[reason]}</p>
    </Section>
  );
}

function HeroPanel({ data }: { data: LandingData }) {
  const hero = data.hero!;
  const topic = data.topics.find((t) => t.id === hero.topicId) ?? null;
  const [set, setSet] = useState<"channel" | "topic">("channel");
  const [width, setWidth] = useState(DESIGN_WIDTH);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = boxRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.max(MIN_WIDTH, Math.round(entry.contentRect.width));
      setWidth((prev) => (Math.abs(next - prev) > 8 ? next : prev));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const isChannel = set === "channel" || topic === null;
  const rates = isChannel ? data.channel.rates : topic.rates;
  const stats = isChannel ? data.channel.stats : topic.stats;
  const { below, others: otherCount, share } = rankAmongOthers(rates, hero.rate);
  const above = hero.rate > stats.median;
  const atMedian = hero.rate === stats.median;
  const channelAbove = hero.rate > data.channel.stats.median;
  const axisMax = data.axisMax;

  const gap = Math.max(6.5, 9 * Math.min(1, width / DESIGN_WIDTH));
  const placed = swarm(withHeroLast(rates, hero.rate), {
    width,
    axisMax,
    cy: CENTRE_Y,
    step: gap,
    minDist: gap,
    tries: 40,
  });
  const heroIndex = rates.length - 1 + (rates.includes(hero.rate) ? 0 : 1);
  const heroDot = placed.find((dot) => dot.index === heroIndex)!;
  const heroX = heroDot.x;

  // Màn hẹp (biểu đồ rộng hơn khung): mở vùng cuộn ở chỗ chấm hero, để câu trả lời và bằng chứng cùng thấy được
  // (ux-reviewer PR 2b, L2/C1). Cuộn tức thời, không hoạt cảnh (hợp reduced-motion)
  useEffect(() => {
    const el = boxRef.current;
    if (!el || el.scrollWidth <= el.clientWidth) return;
    // Căn giữa giữa median và chấm hero (câu trả lời + mốc so cùng thấy), nhưng không cuộn quá mép trái nhãn median (~60px)
    // Ưu tiên chấm hero + nhãn của nó (~90px) luôn trong khung (code-reviewer: bài xa median thì median nhường)
    const medianX = (stats.median / axisMax) * el.scrollWidth;
    const heroPx = (heroX / width) * el.scrollWidth;
    const preferred = Math.min((heroPx + medianX) / 2 - el.clientWidth / 2, medianX - 60);
    // Kẹp 2 phía: bài xa median về bên phải hay bên trái thì chấm hero + nhãn vẫn trong khung
    el.scrollLeft = Math.min(Math.max(0, preferred, heroPx + 90 - el.clientWidth), Math.max(0, heroPx - 90));
  }, [heroX, width, set, stats.median, axisMax]);
  const others = placed.filter((dot) => dot.index !== heroIndex);

  // Câu trả lời sinh từ dữ liệu (handoff §0 loại C), không viết cứng kết luận
  // "do better than usual" = cao hơn median (đúng phép đo, Thy duyệt 2026-10-08) — không có ngưỡng "strong"
  // Tập mang cờ insufficient_data: chỉ mô tả thứ hạng, không Yes/Not (UI-L20260903-small-n-flag)
  const flagged = stats.insufficient_data;
  const unitWord = otherCount === 1 ? "content unit" : "content units";
  const answer = isChannel
    ? otherCount === 0
      ? "It is the only content unit with recorded views so far."
      : flagged
        ? `Its engagement rate is higher than ${share}% of the channel's other content units; too few content units to interpret.`
        : above
          ? `Yes. Its engagement rate is higher than ${share}% of the channel's other content units.`
          : atMedian
            ? "About usual: it sits at the channel median."
            : `Not this time. Its engagement rate is higher than only ${share}% of the channel's other content units.`
    : otherCount === 0
      ? "It is the only content unit with recorded views in its topic."
      : flagged
        ? `Within its topic: higher than ${below} of the other ${otherCount} "${topic.name}" ${unitWord}; too few content units to interpret.`
        : atMedian
          ? "About usual within its topic: it sits at the topic median."
          : above
            ? `${channelAbove && !data.channel.stats.insufficient_data ? "Yes, within its topic too" : "Within its topic, yes"}: higher than ${below} of the other ${otherCount} "${topic.name}" ${unitWord}.`
            : `Not within its topic: higher than ${below} of the other ${otherCount} "${topic.name}" ${unitWord}.`;
  const footNote = isChannel
    ? data.channel.excluded > 0
      ? `${data.channel.excluded} of ${count(data.channel.total)} excluded: no views recorded.`
      : null
    : `${topic.name} (named by Claude) · ${stats.n} ${stats.n === 1 ? "content unit" : "content units"} with recorded views${
        stats.insufficient_data ? " · too few content units to interpret" : ""
      }${topic.excluded > 0 ? ` · ${topic.excluded} excluded: no views recorded` : ""}.`;

  return (
    <Section id="example" ux="hero-panel" n="00" short="One real content unit" title={HERO_QUESTION} purpose={HERO_PURPOSE}>
      <Answer>{answer}</Answer>

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className={TYPE.label}>Compare with</span>
          {/* Nút chung của mọi trang (C2/C4: 44px, aria-pressed); không có topic → chỉ còn 1 lựa chọn */}
          <ToggleGroup
            label="Comparison set"
            options={[
              { key: "channel", label: `All content units · ${count(data.channel.stats.n)}` },
              ...(topic ? [{ key: "topic" as const, label: `Same topic · ${count(topic.stats.n)}` }] : []),
            ]}
            value={set}
            onChange={setSet}
          />
        </div>

        {/* Dưới 720px biểu đồ cuộn ngang trong vùng có focus bàn phím (A1: vùng cuộn dùng được bằng phím mũi tên) */}
        <div
          ref={boxRef}
          tabIndex={0}
          role="region"
          aria-label="Engagement rate of every content unit, with this one highlighted"
          className="overflow-x-auto rounded-md px-4"
        >
          <div className="relative h-[250px] min-w-[720px] tabular-nums">
            <div
              className="absolute bottom-[34px] top-7 rounded-md bg-bg-surface"
              style={{
                left: axisPct(stats.iqr_low, axisMax),
                width: axisPct(stats.iqr_high - stats.iqr_low, axisMax),
              }}
            />
            <div
              className="absolute bottom-[34px] top-5 w-0.5 bg-text-primary"
              style={{ left: axisPct(stats.median, axisMax) }}
            />
            <span
              className={`absolute top-0 -translate-x-1/2 whitespace-nowrap ${TYPE.mono} font-medium text-text-primary`}
              style={{ left: axisPct(stats.median, axisMax) }}
            >
              median {pct(stats.median)}
            </span>
            <span
              className={`absolute bottom-10 whitespace-nowrap pl-2 ${TYPE.mono} text-text-secondary`}
              style={{ left: axisPct(stats.median, axisMax) }}
            >
              middle half {stats.iqr_low.toFixed(2)}–{pct(stats.iqr_high)}
            </span>
            {others.map((dot) => (
              <div
                key={dot.index}
                aria-hidden="true"
                className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full bg-text-muted"
                style={{
                  left: `${(dot.x / width) * 100}%`,
                  top: dot.y,
                  width: Math.round(gap - 1),
                  height: Math.round(gap - 1),
                  opacity: isChannel ? 1 : 0.5,
                }}
              />
            ))}
            <div
              aria-hidden="true"
              className="absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-amber-600 shadow-[0_0_0_1px_var(--amber-600)]"
              style={{ left: `${(heroDot.x / width) * 100}%`, top: heroDot.y }}
            />
            <div
              className="absolute flex -translate-x-1/2 flex-col items-center gap-0.5 whitespace-nowrap"
              style={{ left: `${(heroDot.x / width) * 100}%`, top: heroDot.y - 52 }}
            >
              <span className="text-[13px] font-semibold text-amber-700">This content unit · {pct(hero.rate)}</span>
              {otherCount > 0 ? (
                <span className={`${TYPE.label} text-text-secondary`}>
                  higher than {below} of the other {count(otherCount)}
                </span>
              ) : null}
            </div>
            <div className="absolute inset-x-0 bottom-[22px] h-px bg-rule" />
            {ticks(axisMax).map((tick) => (
              <span
                key={tick}
                className={`absolute bottom-0 -translate-x-1/2 ${TYPE.mono} text-text-muted`}
                style={{ left: axisPct(tick, axisMax) }}
              >
                {tick}%
              </span>
            ))}
          </div>
        </div>
        {footNote ? <p className={`m-0 ${TYPE.note}`}>{footNote}</p> : null}
      </div>

      <MethodSection
        steps={[
          {
            title: "Engagement rate",
            plain: "Interactions on a content unit's opening post per 100 views of the opening post, so content units with few and many views can be placed on one scale.",
            formula: "engagement rate = (likes + replies + reposts + quotes) ÷ views × 100",
          },
          {
            title: "Dots",
            plain: `Each dot is one content unit with recorded views${isChannel ? "" : " in the same topic"}, stacked so none overlap; the highlighted dot is this one.`,
          },
          {
            title: "Median and middle half",
            plain: "The median is the rate of the middle content unit once they are sorted by rate. The middle half runs from the 25th to the 75th percentile (Q₁ to Q₃); the grey band shows it.",
            formula: "middle half = [ Q_1 , Q_3 ]",
          },
          {
            title: "Rank",
            plain: "Yes means its rate is above the median. The percentage counts the other content units with a lower rate (ties not counted), as a share of all the others, rounded down.",
            formula: "share = ⌊ below × 100 ÷ others ⌋",
          },
        ]}
        limits={[
          "Rates use the **latest counts** (re-read every 4 hours), so newer content units have had less time to collect views and interactions.",
          "Interactions on the **follow-up parts are not counted**; only the opening post's are.",
          "One content unit is **described, not tested**: its rank does not say why it did well or badly.",
          `Content units without recorded views are left out${data.summary.latest_snapshot_at ? `; data as of ${dayMonthYear(data.summary.latest_snapshot_at)}` : ""}.`,
        ]}
      />
    </Section>
  );
}
