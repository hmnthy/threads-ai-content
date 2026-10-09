"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { BrandLogo } from "@/components/BrandLogo";
import { MethodBlock, MethodButton, PANEL } from "@/components/LandingParts";
import {
  HERO_QUESTION,
  axisPct,
  count,
  dayMonthYear,
  monthYear,
  pct,
  rankAmongOthers,
  swarm,
  ticks,
  type LandingData,
} from "@/lib/landing";

const MIN_WIDTH = 720; // dưới mức này beeswarm cuộn ngang trong container (UI-L20260829-mobile)
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
        {/* Chỗ DUY NHẤT logo chuyển động; reduced-motion → bản tĩnh qua <picture> (ADR-0021) */}
        <BrandLogo variant="lockup-animated" height={64} />
        <h1 className="m-0 text-[clamp(44px,6.4vw,76px)] font-extrabold leading-none tracking-[-0.04em] [text-wrap:balance]">
          The algorithm, read back to you.
        </h1>
        <p className="m-0 max-w-[640px] text-lg leading-[1.6] text-text-secondary [text-wrap:pretty]">
          Unthreaded shows how each post on a Threads channel did compared with the rest of that
          channel, not with Threads as a whole. Every figure says how many posts it rests on.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link
            href="/overview"
            className="flex h-12 items-center rounded-full bg-amber-600 px-[22px] text-[15px] font-semibold text-white hover:bg-amber-700"
          >
            View live dashboard
          </Link>
          <a
            href="#method"
            className="flex h-12 items-center rounded-full border border-border-hairline bg-bg-card px-[22px] text-[15px] font-medium text-text-primary"
          >
            See how it works
          </a>
        </div>
      </div>
      {data ? <ChannelStats data={data} /> : null}
      {data?.hero ? (
        <HeroPanel data={data} />
      ) : (
        <HeroEmpty reason={data === null ? "offline" : data.heroFound ? "no-views" : "missing"} />
      )}
    </section>
  );
}

// Dải thống kê kênh (Thy duyệt 2026-10-08): định nghĩa mẫu số MỘT lần trước bài mẫu, để các câu
// sau chỉ cần nói "the channel's posts". Mọi số từ API: /pipeline/summary, /analytics/overview.
function ChannelStats({ data }: { data: LandingData }) {
  const run = data.summary.latest_cluster_run;
  const items = [
    {
      value: count(data.summary.content_units),
      label: data.firstPostAt ? `posts since ${monthYear(data.firstPostAt)}` : "posts",
    },
    { value: count(data.channel.stats.n), label: "with recorded views" },
    {
      value: data.channel.stats.n > 0 ? pct(data.channel.stats.median) : "—",
      label: "median engagement rate",
    },
    ...(run ? [{ value: String(run.n_clusters), label: "topics" }] : []),
  ];
  return (
    <div className="mt-12 flex flex-col items-center gap-3">
      <dl className="m-0 flex flex-wrap justify-center gap-x-10 gap-y-4">
        {items.map((item) => (
          <div key={item.label} className="flex flex-col items-center gap-0.5">
            <dt className="order-2 text-[13px] text-text-secondary">{item.label}</dt>
            <dd className="order-1 m-0 text-[28px] font-bold tabular-nums tracking-[-0.02em]">
              {item.value}
            </dd>
          </div>
        ))}
      </dl>
      {data.summary.latest_snapshot_at ? (
        <span className="font-mono text-xs text-text-muted">
          Data as of {dayMonthYear(data.summary.latest_snapshot_at)}
        </span>
      ) : null}
    </div>
  );
}

const EMPTY_REASON = {
  offline: "The data service is not reachable right now. Reload in a moment.",
  "no-views": "This post has no recorded views yet, so it cannot be placed against the channel.",
  missing: "This post is not in the database yet, so it cannot be placed against the channel.",
} as const;

function HeroEmpty({ reason }: { reason: keyof typeof EMPTY_REASON }) {
  return (
    <div className={`${PANEL} mt-10 gap-2`}>
      <span className="text-[13px] font-semibold text-amber-600">{HERO_QUESTION}</span>
      <span className="text-base text-text-secondary">
        {EMPTY_REASON[reason]}
      </span>
    </div>
  );
}

function HeroPanel({ data }: { data: LandingData }) {
  const hero = data.hero!;
  const topic = data.topics.find((t) => t.id === hero.topicId) ?? null;
  const [set, setSet] = useState<"channel" | "topic">("channel");
  const [methodOpen, setMethodOpen] = useState(false);
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
  const others = placed.filter((dot) => dot.index !== heroIndex);

  // Câu trả lời sinh từ dữ liệu (handoff §0 loại C), không viết cứng kết luận
  // "do better than usual" = cao hơn median (đúng phép đo, Thy duyệt 2026-10-08) — không có ngưỡng "strong"
  // Tập mang cờ insufficient_data: chỉ mô tả thứ hạng, không Yes/Not (UI-L20260903-small-n-flag)
  const flagged = stats.insufficient_data;
  const postWord = otherCount === 1 ? "post" : "posts";
  const answer = isChannel
    ? otherCount === 0
      ? "It is the only post with recorded views so far."
      : flagged
        ? `Its engagement rate is higher than ${share}% of the channel's other posts; too few posts to interpret.`
        : above
          ? `Yes. Its engagement rate is higher than ${share}% of the channel's other posts.`
          : atMedian
            ? "About usual: it sits at the channel median."
            : `Not this time. Its engagement rate is higher than only ${share}% of the channel's other posts.`
    : otherCount === 0
      ? "It is the only post with recorded views in its topic."
      : flagged
        ? `Within its topic: higher than ${below} of the other ${otherCount} "${topic.name}" ${postWord}; too few posts to interpret.`
        : atMedian
          ? "About usual within its topic: it sits at the topic median."
          : above
            ? `${channelAbove && !data.channel.stats.insufficient_data ? "Yes, within its topic too" : "Within its topic, yes"}: higher than ${below} of the other ${otherCount} "${topic.name}" ${postWord}.`
            : `Not within its topic: higher than ${below} of the other ${otherCount} "${topic.name}" ${postWord}.`;
  const footNote = isChannel
    ? data.channel.excluded > 0
      ? `${data.channel.excluded} of ${count(data.channel.total)} excluded: no views recorded`
      : null
    : `${topic.name} (named by Claude) · ${topic.id} · ${stats.n} posts with recorded views${
        stats.insufficient_data ? " · too few posts to interpret" : ""
      }${topic.excluded > 0 ? ` · ${topic.excluded} excluded: no views recorded` : ""}`;

  const toggle = (value: "channel" | "topic", label: string, disabled = false) => (
    <button
      type="button"
      onClick={() => setSet(value)}
      aria-pressed={set === value}
      disabled={disabled}
      className={`h-[38px] cursor-pointer whitespace-nowrap rounded-full border-0 px-3.5 text-[13px] font-medium disabled:cursor-not-allowed disabled:opacity-50 ${
        set === value ? "bg-text-primary text-white" : "bg-transparent text-text-secondary"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className={`${PANEL} mt-10 gap-5`}>
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="flex max-w-[680px] flex-col gap-1.5">
          <span className="text-[13px] font-semibold text-amber-600">{HERO_QUESTION}</span>
          <span className="text-2xl font-bold leading-[1.3] tracking-[-0.02em]">{answer}</span>
          <span className="text-[13px] text-text-secondary">
            Engagement rate: likes, replies, reposts and quotes per 100 views.
          </span>
        </div>
        <div role="group" aria-label="Comparison set" className="flex rounded-full bg-bg-surface p-[3px]">
          {toggle("channel", `All posts · ${count(data.channel.stats.n)}`)}
          {topic
            ? toggle("topic", `Same topic · ${count(topic.stats.n)}`)
            : toggle("topic", "Same topic · none", true)}
        </div>
      </div>

      <div ref={boxRef} className="overflow-x-auto px-4">
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
            className="absolute top-0 -translate-x-1/2 whitespace-nowrap font-mono text-xs font-medium text-text-primary"
            style={{ left: axisPct(stats.median, axisMax) }}
          >
            median {pct(stats.median)}
          </span>
          <span
            className="absolute bottom-10 whitespace-nowrap pl-2 font-mono text-[11.5px] text-text-secondary"
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
            <span className="text-[13px] font-bold text-amber-600">This post · {pct(hero.rate)}</span>
            {otherCount > 0 ? (
              <span className="text-xs text-text-secondary">
                higher than {below} of the other {count(otherCount)}
              </span>
            ) : null}
          </div>
          <div className="absolute inset-x-0 bottom-[22px] h-px bg-rule" />
          {ticks(axisMax).map((tick) => (
            <span
              key={tick}
              className="absolute bottom-0 -translate-x-1/2 font-mono text-[11.5px] text-text-muted"
              style={{ left: axisPct(tick, axisMax) }}
            >
              {tick}%
            </span>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-bg-surface pt-3">
        <span className="text-[12.5px] text-text-secondary">{footNote}</span>
        <MethodButton open={methodOpen} onToggle={() => setMethodOpen((open) => !open)} />
      </div>
      {methodOpen ? (
        <div className="-mt-2">
          <MethodBlock
            formula={`engagement rate = (likes + replies + reposts + quotes) / views × 100 · one dot per post · middle half = IQR (interquartile range)${
              data.summary.latest_snapshot_at
                ? ` · data as of ${dayMonthYear(data.summary.latest_snapshot_at)}`
                : ""
            }`}
            limits="Limits: rate uses the latest snapshot, so newer posts have had less time to collect views. A single post is described, not tested."
          />
        </div>
      ) : null}
    </div>
  );
}
