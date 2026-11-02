"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getAnalyticsOverview, type AnalyticsOverview, type TopPostEntry } from "@/lib/api";
import {
  ActionButton,
  AnswerRow,
  LoadError,
  MethodSection,
  Section,
  SubSection,
  ToggleGroup,
  topicOfUnit,
  TYPE,
  UnitText,
  type KeyNumber,
} from "@/components/AppBlock";
import { hasPosts, rateNote } from "@/components/DistributionCaption";
import { PostingTimeHeatmap } from "@/components/PostingTimeHeatmap";
import { UnitPicker } from "@/components/UnitPicker";
import { UnitVsChannel, type PickableUnit } from "@/components/UnitVsChannel";
import { ANALYTICS_SECTIONS, shortOf } from "@/lib/appSections";
import { formatPostDateTimeParis } from "@/lib/dates";
import { count, HERO_ENGLISH, HERO_POST_ID, pct, RATE_INFO, type LandingData, type RateKey } from "@/lib/landing";

type MetricKey = RateKey;

// Mỗi tab = 1 tỉ lệ; tên tab, tên cột và công thức MỘT nguồn với khối 02 (`RATE_INFO` — code-reviewer 2026-11-02: 2
// bảng định nghĩa sẽ lệch nhau; copy-reviewer 2026-10-31: tab/cột/KPI từng gọi 3 kiểu). `digits`: 2 cho engagement, 3
// cho share + conversation (cùng quy ước bảng so sánh của /topics)
const RATES = (Object.keys(RATE_INFO) as RateKey[]).map((key) => ({ key, ...RATE_INFO[key] }));

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

// Trang /analytics theo khuôn khối chung (Thy 2026-10-31): 01 xếp hạng theo tỉ lệ (không phải kiểm định), 02 một content
// unit so với kênh (Thy 2026-11-02, mô tả), 03 giờ và ngày đăng (mô tả). Bảng xếp hạng chỉ gồm content unit có views ≥
// sàn (ADR-0023 1f, sàn tính ở backend)
export function AnalyticsBreakdown({
  topicOf,
  topicCount,
  minPosts,
  comparison,
}: {
  topicOf: Record<string, string | null> | null;
  topicCount: number | null;
  minPosts: number | null;
  // Khối 02: dữ liệu dựng phía server (cùng hàm với landing); null = không đọc được lúc tải trang
  comparison: { data: LandingData; units: PickableUnit[] } | null;
}) {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [active, setActive] = useState<MetricKey>("engagement");
  // Bài mặc định = bài mẫu của panel hero landing (cùng câu trả lời ở 2 nơi), không có thì bài mới nhất. Tính khi render,
  // không trong useState: `comparison` có thể đổi từ null sang có dữ liệu sau "Try again" (router.refresh — code-reviewer)
  const [picked, setPicked] = useState<string | null>(null);
  const units = comparison?.units ?? [];
  const pickedId = picked ?? (units.find((unit) => unit.id === HERO_POST_ID) ?? units[0])?.id ?? null;
  // Link "#unit" (từ landing): khối 02 có sẵn trong HTML server nên trình duyệt cuộn tới ngay, nhưng khối 01 tải sau sẽ
  // đẩy nó xuống — cuộn lại một lần khi khối 01 đã hiện (code-reviewer 2026-11-02)
  const hashScrolled = useRef(false);
  // Tỉ lệ của khối 02 (Thy 2026-11-02: cả 3 tỉ lệ) — riêng với tab của bảng top, nhưng nút "Compare" mang tab đang
  // xem sang, để khối 02 so đúng thước đo người đọc vừa nhìn
  const [unitRate, setUnitRate] = useState<MetricKey>("engagement");
  const pickable = new Set(comparison?.units.map((unit) => unit.id) ?? []);
  // Nút "Compare" của bảng top: chọn bài + tỉ lệ, cuộn tới khối 02 (tức thời — hợp reduced-motion) và chuyển focus
  // vào tiêu đề khối, để phím Tab tiếp theo đi tiếp trong khối 02 chứ không kéo trang về bảng (ux-reviewer A2)
  const compare = (id: string) => {
    setPicked(id);
    setUnitRate(active);
    document.getElementById("unit")?.scrollIntoView({ block: "start" });
    const title = document.getElementById("unit-title");
    if (title) {
      title.setAttribute("tabindex", "-1");
      title.focus({ preventScroll: true });
    }
  };

  useEffect(() => {
    getAnalyticsOverview()
      .then((overview) => {
        setData(overview);
        setFailed(false);
      })
      .catch((err: unknown) => {
        console.error("analytics: could not load data", err);
        setFailed(true);
      });
  }, [attempt]);

  // Người đọc đã tự cuộn / gõ phím trong lúc khối 01 còn tải → không kéo trang về khối 02 nữa (code-reviewer)
  useEffect(() => {
    const stop = () => {
      hashScrolled.current = true;
    };
    const events = ["wheel", "touchmove", "keydown"] as const;
    for (const name of events) window.addEventListener(name, stop, { once: true, passive: true });
    return () => {
      for (const name of events) window.removeEventListener(name, stop);
    };
  }, []);

  useEffect(() => {
    if (data === null || hashScrolled.current) return;
    hashScrolled.current = true;
    if (window.location.hash === "#unit") document.getElementById("unit")?.scrollIntoView({ block: "start" });
  }, [data]);

  // Khối 02 chỉ cần dữ liệu phía server → luôn hiện, kể cả khi khối 01 + 03 (dữ liệu tải ở trình duyệt) đang tải hay lỗi.
  // `key` cố định: React giữ nguyên khối (ô tìm, tập so, bề rộng biểu đồ) khi trang đổi từ nhánh đang tải sang nhánh đủ
  // dữ liệu, không phụ thuộc vị trí của khối giữa các anh em (code-reviewer 2026-11-02)
  const unitSection = (
    <Section
      key="unit"
      id="unit"
      n="02"
      short={shortOf(ANALYTICS_SECTIONS, "unit")}
      title="Did the content unit you pick do better than the channel's usual content unit?"
      purpose="Pick a content unit with recorded views. It is ranked on the rate you choose, against the rest of the channel or the rest of its own topic."
    >
      <UnitBlock
        comparison={comparison}
        picked={pickedId}
        onPick={setPicked}
        rate={unitRate}
        onRate={setUnitRate}
        topicOf={topicOf}
        topicCount={topicCount}
      />
    </Section>
  );

  if (failed || data === null) {
    return (
      <div className="flex flex-col gap-10">
        {failed ? (
          // Câu cho người xem + nút thử lại (ux-reviewer S12, N9)
          <LoadError onRetry={() => setAttempt((n) => n + 1)} />
        ) : (
          <div className={`rounded-xl border border-border-hairline bg-bg-card p-6 ${TYPE.body}`}>Loading analytics…</div>
        )}
        {unitSection}
      </div>
    );
  }

  const rate = RATES.find((item) => item.key === active)!;
  const list = active === "engagement" ? data.top_by_engagement : active === "share" ? data.top_by_share_rate : data.top_by_conversation;
  // Phân phối toàn kênh của đúng tỉ lệ đang chọn (ADR-0031) — câu trả lời so top với kênh
  const channel = active === "engagement" ? data.engagement : active === "share" ? data.share_rate : data.conversation;
  const high = list.length > 0 ? list[0].metrics[rate.field] : null;
  const low = list.length > 0 ? list[list.length - 1].metrics[rate.field] : null;
  const maxValue = Math.max(...list.map((entry) => entry.metrics[rate.field]), 0.0001);
  // views là số nguyên: ≥ P25 (VD 1,755.5) ⇔ ≥ làm tròn lên
  const floor = data.views_floor === null ? null : Math.ceil(data.views_floor);
  const ranked = data.post_count - data.below_views_floor;

  const numbers: KeyNumber[] = [
    {
      value: count(data.post_count),
      label: "content units with recorded views",
      note:
        data.excluded_no_views > 0
          ? `${data.excluded_no_views} of ${count(data.post_count + data.excluded_no_views)} excluded: no views recorded.`
          : undefined,
    },
    ...(floor === null
      ? []
      : [
          {
            value: count(ranked),
            label: "ranked",
            note: `At least ${count(floor)} views each.`,
            share: { part: ranked, whole: data.post_count, of: count(data.post_count) },
          },
        ]),
    {
      value: hasPosts(channel) ? pct(channel.median, rate.digits) : "—",
      label: `channel median ${rate.label.toLowerCase()}`,
      note: rateNote(channel, rate.digits, "No content unit has recorded views yet."),
    },
  ];

  return (
    <div className="flex flex-col gap-10">
      <Section
        id="ranking"
        n="01"
        short={shortOf(ANALYTICS_SECTIONS, "ranking")}
        title="Which content units rank highest on each rate?"
        purpose="Every content unit collected so far (no time window) with enough views to compare, sorted by the rate you choose."
      >
        <AnswerRow
          answer={
            high === null || low === null
              ? "No content unit has recorded views yet."
              : `By ${rate.label.toLowerCase()}, ${
                  // 1 dòng hoặc min = max: không viết "from X to X" (code-reviewer)
                  list.length === 1
                    ? `the only ranked content unit has ${pct(high, rate.digits)}`
                    : pct(low, rate.digits) === pct(high, rate.digits)
                      ? `the top ${list.length} all have ${pct(high, rate.digits)}`
                      : `the top ${list.length} range from ${pct(low, rate.digits)} to ${pct(high, rate.digits)}`
                }${
                  hasPosts(channel)
                    ? `, against a median of ${pct(channel.median, rate.digits)} across all ${count(channel.n)} content units with recorded views`
                    : ""
                }.`
          }
          points={[
            "A **ranking, not a test**: a higher rate here does not show that a content unit differs from the rest of the channel.",
            floor === null
              ? "Every content unit with recorded views is ranked: there are too few yet to set a minimum number of views."
              : `**${count(ranked)} of ${count(data.post_count)}** content units with recorded views have at least ${count(floor)} views and are ranked.`,
            floor === null
              ? null
              : `The cut-off is the **25th percentile of views** among content units with recorded views, recomputed as new views come in; the ${count(data.below_views_floor)} below it are left out.`,
            "Below the cut-off, a few interactions move a rate too much for a fair comparison.",
          ]}
          keyNumbers={numbers}
        />
        <SubSection
          title={`Top ${list.length} by ${rate.label.toLowerCase()}`}
          note={`${rate.label} = ${rate.formula}`}
          action={<ToggleGroup label="Rate to rank by" options={RATES} value={active} onChange={setActive} />}
        >
          <TopTable
            entries={list}
            field={rate.field}
            rateLabel={rate.label}
            digits={rate.digits}
            maxValue={maxValue}
            topicOf={topicOf}
            topicCount={topicCount}
            onCompare={compare}
            canCompare={(id) => pickable.has(id)}
          />
        </SubSection>
        <MethodSection
          steps={[
            {
              title: "Rates",
              plain: "The opening post's interactions divided by its views.",
              formula: RATES.map((item) => `${item.label.toLowerCase()} = ${item.formula}`),
            },
            {
              title: "Median and middle half",
              plain: "The median is the rate of the middle content unit once they are sorted by that rate. The middle half runs from the 25th to the 75th percentile (Q₁ to Q₃); its width, Q₃ − Q₁, is the interquartile range (IQR); this page shows the range itself, Q₁ to Q₃.",
              formula: ["middle half = [ Q_1 , Q_3 ]", "IQR = Q_3 − Q_1"],
            },
            {
              title: "Views cut-off",
              plain: "Only content units with at least as many views as the 25th percentile are ranked. The percentile is taken over content units with recorded views and recomputed whenever views are re-read.",
              formula: "cut-off = P_25( views )",
            },
            {
              title: "Ranking",
              plain: "Content units at or above the cut-off, sorted by the chosen rate; the table shows the top of the list. Each bar's length is its rate divided by the largest rate in the list.",
              formula: "bar = rate ÷ max(rate in the list)",
            },
          ]}
          limits={[
            "A ranking describes the content units; it **does not test** whether a rate differs from the rest of the channel.",
            "Views and interactions are counted to date, so older content units have had more time to collect them.",
            "The cut-off moves as new views come in, so a content unit near it can enter or leave the ranking.",
          ]}
        />
      </Section>

      {unitSection}

      <Section
        id="posting-time"
        n="03"
        short={shortOf(ANALYTICS_SECTIONS, "posting-time")}
        title="How does engagement rate vary with posting hour and weekday?"
        purpose="All content units with recorded views, placed on a Paris or a Vietnam clock; every cell shows a median and how many content units it rests on."
      >
        <PostingTimeHeatmap
          timezones={data.timezones}
          excludedNoViews={data.excluded_no_views}
          totalUnits={data.post_count + data.excluded_no_views}
          minPosts={minPosts}
        />
      </Section>
    </div>
  );
}

// Khối 02: ô chọn bài + dòng bài đang chọn (tên topic tiếng Anh trên chữ gốc, B2) + phần thân dùng chung với panel
// hero của landing (`UnitVsChannel`)
function UnitBlock({
  comparison,
  picked,
  onPick,
  rate,
  onRate,
  topicOf,
  topicCount,
}: {
  comparison: { data: LandingData; units: PickableUnit[] } | null;
  picked: string | null;
  onPick: (id: string) => void;
  rate: MetricKey;
  onRate: (rate: MetricKey) => void;
  topicOf: Record<string, string | null> | null;
  topicCount: number | null;
}) {
  const router = useRouter();
  if (comparison === null) {
    // Dữ liệu khối dựng phía server → thử lại = tải lại dữ liệu server của trang (C5: lỗi có nút thử lại)
    return <LoadError what="This block's data could not be loaded." onRetry={() => router.refresh()} />;
  }
  const unit = comparison.units.find((item) => item.id === picked) ?? null;
  if (unit === null) {
    return <p className={`m-0 ${TYPE.body}`}>No content unit has recorded views yet.</p>;
  }
  return (
    <>
      <div className="flex flex-col gap-4">
        <UnitPicker
          units={comparison.units}
          value={unit.id}
          onChange={onPick}
          rate={rate}
          topicOf={topicOf}
          topicCount={topicCount}
        />
        {/* Không viền: card của khối đã là hộp (§3 — không hộp viền lồng trong hộp) */}
        <div className="flex flex-col gap-1.5">
          <span className={TYPE.eyebrow}>SELECTED CONTENT UNIT</span>
          <UnitText text={unit.text} topic={topicOfUnit(topicOf, unit.id)} topicCount={topicCount} />
          {/* Bài mẫu của landing có sẵn nghĩa tiếng Anh đã duyệt (B2) — nói rõ vì sao nó được chọn sẵn */}
          {unit.id === HERO_POST_ID ? (
            <span className={TYPE.note}>Preselected: the example from the home page (&ldquo;{HERO_ENGLISH}&rdquo;).</span>
          ) : null}
          <span className={`${TYPE.mono} text-text-secondary`}>
            {RATES.map((item) => `${pct(unit.rates[item.key], item.digits)} ${item.label.toLowerCase()}`).join(" · ")} ·{" "}
            {count(unit.views)} views
            {unit.timestamp ? ` · published ${formatPostDateTimeParis(unit.timestamp)} Paris time` : ""}
          </span>
        </div>
      </div>
      {/* Đổi bài / tỉ lệ giữ nguyên tập so người đọc đã chọn; bài không có topic tự về "All content units" */}
      <UnitVsChannel
        data={comparison.data}
        topicId={unit.topicId}
        value={unit.rates[rate]}
        rate={rate}
        keyNumbers
        controls={
          <div className="flex flex-wrap items-center gap-3">
            <span className={TYPE.label}>Rate</span>
            <ToggleGroup label="Rate to compare" options={RATES} value={rate} onChange={onRate} />
          </div>
        }
      />
    </>
  );
}

function TopTable({
  entries,
  field,
  rateLabel,
  digits,
  maxValue,
  topicOf,
  topicCount,
  onCompare,
  canCompare,
}: {
  entries: TopPostEntry[];
  field: keyof TopPostEntry["metrics"];
  rateLabel: string;
  digits: number;
  maxValue: number;
  topicOf: Record<string, string | null> | null;
  topicCount: number | null;
  onCompare: (id: string) => void;
  canCompare: (id: string) => boolean;
}) {
  // Nút đưa 1 dòng sang khối 02 (nút chung `ActionButton`, C2); tên đọc được nói rõ bài nào, so theo tỉ lệ nào, đi
  // đâu (A1) — hạng đọc thành số ("3", không "zero three")
  const compareButton = (entry: TopPostEntry, rank: string) =>
    canCompare(entry.id) ? (
      <ActionButton
        onClick={() => onCompare(entry.id)}
        // không nói "with the channel": khối 02 có thể đang so trong topic (code-reviewer 2026-11-02)
        aria-label={`Compare content unit ${Number(rank)} by ${rateLabel.toLowerCase()}, in block 02`}
        className="self-start"
      >
        Compare ↓
      </ActionButton>
    ) : null;
  if (entries.length === 0) {
    return <p className={`m-0 ${TYPE.body}`}>No content unit has recorded views yet.</p>;
  }
  const rows = entries.map((entry, index) => {
    const value = entry.metrics[field];
    const topic = topicOfUnit(topicOf, entry.id);
    return {
      entry,
      rank: (index + 1).toString().padStart(2, "0"),
      value,
      width: maxValue > 0 ? Math.max((value / maxValue) * 100, 2) : 0,
      text: entry.text === null ? null : truncate(entry.text, 110),
      topic,
    };
  });
  const bar = (width: number) => (
    <span aria-hidden="true" className="h-1.5 w-16 overflow-hidden rounded-full bg-bg-surface">
      <span className="block h-full rounded-full bg-amber-fill" style={{ width: `${width}%` }} />
    </span>
  );
  return (
    <>
      {/* Dưới sm: mỗi dòng một thẻ xếp dọc như danh sách Overview — không phải cuộn ngang mới thấy views, ngày
          (ux-reviewer N4) */}
      <ol className="m-0 flex list-none flex-col p-0 sm:hidden">
        {rows.map((row) => (
          <li key={row.entry.id} className="flex flex-col gap-2 border-t border-border-hairline py-3 first:border-t-0">
            <span className="flex items-center gap-3">
              <span className={`${TYPE.mono} text-text-muted`}>{row.rank}</span>
              {bar(row.width)}
              <span className={`${TYPE.mono} font-semibold text-text-primary`}>{pct(row.value, digits)}</span>
            </span>
            <UnitText text={row.text} topic={row.topic} topicCount={topicCount} size="cell" />
            <span className={`${TYPE.mono} text-text-secondary`}>
              {/* "· Paris time" như mọi dòng dữ liệu; tiêu đề bảng dùng "(Paris time)" (Thy 2026-11-02) */}
              {count(row.entry.metrics.popularity_index)} views · {formatPostDateTimeParis(row.entry.timestamp)}{" "}
              <span className="whitespace-nowrap">· Paris time</span>
            </span>
            {compareButton(row.entry, row.rank)}
          </li>
        ))}
      </ol>
      {/* Từ sm: bảng; cuộn ngang được khi hẹp → chọn được bằng bàn phím (axe scrollable-region-focusable) */}
      <div
        className="hidden overflow-x-auto sm:block"
        tabIndex={0}
        role="region"
        aria-label={`Top content units by ${rateLabel.toLowerCase()}`}
      >
        <table className="w-full min-w-[640px] border-collapse">
          <thead>
            {/* align-bottom: tiêu đề 1 dòng và 2 dòng chung đường chân, sát hàng số liệu (ux-reviewer L3) */}
            <tr className="border-b border-border-hairline text-left align-bottom">
              <th scope="col" className={`py-2.5 pr-3 ${TYPE.th}`}>#</th>
              <th scope="col" className={`py-2.5 pr-4 ${TYPE.th}`}>{rateLabel}</th>
              <th scope="col" className={`py-2.5 pr-4 ${TYPE.th}`}>Content unit</th>
              <th scope="col" className={`py-2.5 pr-4 text-right ${TYPE.th}`}>Views</th>
              <th scope="col" className={`py-2.5 pr-4 ${TYPE.th}`}>Published (Paris time)</th>
              <th scope="col" className={`py-2.5 ${TYPE.th}`}>
                <span className="sr-only">Compare in block 02</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.entry.id} className="border-t border-border-hairline align-baseline hover:bg-bg-sunken">
                <td className={`py-3 pr-3 ${TYPE.mono} text-text-muted`}>{row.rank}</td>
                <td className="py-3 pr-4">
                  <span className="flex items-center gap-2">
                    {bar(row.width)}
                    <span className={`${TYPE.mono} font-semibold text-text-primary`}>{pct(row.value, digits)}</span>
                  </span>
                </td>
                <td className="max-w-[440px] py-3 pr-4">
                  <UnitText text={row.text} topic={row.topic} topicCount={topicCount} size="cell" />
                </td>
                <td className={`py-3 pr-4 text-right ${TYPE.mono} text-text-secondary`}>
                  {count(row.entry.metrics.popularity_index)}
                </td>
                <td className={`whitespace-nowrap py-3 pr-4 ${TYPE.mono} text-text-secondary`}>
                  {formatPostDateTimeParis(row.entry.timestamp)}
                </td>
                {/* pr-1: vòng focus 2px của nút không bị khung cuộn ngang của bảng cắt (ux-reviewer A2) */}
                <td className="py-1.5 pr-1 text-right align-top">{compareButton(row.entry, row.rank)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
