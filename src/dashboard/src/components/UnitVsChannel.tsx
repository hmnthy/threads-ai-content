"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Answer, AnswerRow, MethodSection, TYPE, ToggleGroup, type KeyNumber } from "@/components/AppBlock";
import { hasPosts, rateNote } from "@/components/DistributionCaption";
import {
  axisPct,
  count,
  dayMonthYear,
  pct,
  RATE_INFO,
  rankAmongOthers,
  rateAxis,
  swarm,
  ticks,
  type LandingData,
  type RateKey,
} from "@/lib/landing";

// Một content unit đặt vào phân phối một tỉ lệ của kênh (hoặc của topic của nó) — MỘT component cho panel hero của
// landing (bài mẫu cố định, engagement rate) và khối 02 của /analytics (người đọc chọn bài và tỉ lệ — Thy 2026-11-02:
// cả 3 tỉ lệ): cùng phép xếp hạng, cùng câu trả lời, cùng Method (C2; promise-audit 2026-11-02: landing hứa "how each
// content unit … did compared with the rest of that channel" mà ruột chưa cho tra bài bất kỳ). Thứ hạng + median/IQR/n
// của tập so đều mô tả, không kiểm định.

const MIN_WIDTH = 720; // dưới mức này beeswarm cuộn ngang trong vùng cuộn có focus bàn phím (UI-L20260829-mobile)
const DESIGN_WIDTH = 1136; // bề rộng mockup: khoảng cách chấm 9px
const CENTRE_Y = 112;
// Nửa bề rộng ước lượng của chú thích "This content unit · x%" / "higher than k of the other n" (px) — dưới mức này
// tính từ mép thì chú thích căn theo mép thay vì căn giữa trên chấm. Ước lượng trình bày, không phải số liệu
const LABEL_HALF = 110;

// Một dòng của ô chọn bài ở /analytics: chỉ content unit có views (bài không views không đặt được lên trục)
export interface PickableUnit {
  id: string;
  topicId: string | null; // topic ở lần gom cụm mới nhất; null = unclustered hoặc chưa gom cụm
  rates: Record<RateKey, number>; // 3 tỉ lệ của bài mở đầu (%), từ /content-units
  text: string; // dòng đầu, chữ gốc (tiếng Việt / Pháp) — luôn hiện kèm tên topic tiếng Anh (B2)
  timestamp: string | null;
  views: number;
}

// Bỏ đúng 1 lần giá trị của bài được chọn khỏi tập rồi thêm vào cuối: bài đó chiếm 1 chỗ trong swarm như mọi chấm
// khác nhưng được vẽ riêng
function withSelectedLast(rates: number[], selectedRate: number): number[] {
  const i = rates.indexOf(selectedRate);
  return [...(i === -1 ? rates : [...rates.slice(0, i), ...rates.slice(i + 1)]), selectedRate];
}

export function UnitVsChannel({
  data,
  topicId,
  value,
  rate = "engagement",
  keyNumbers = false,
  controls,
  footer,
}: {
  data: LandingData;
  topicId: string | null;
  value: number; // tỉ lệ `rate` của bài được chọn (%)
  rate?: RateKey;
  // Hộp Key numbers cạnh câu trả lời — chỉ /analytics (Thy 2026-11-02); landing có dải số kênh ngay trên panel hero
  keyNumbers?: boolean;
  controls?: ReactNode; // nút thêm trên cùng hàng "Compare with" (VD chọn tỉ lệ ở /analytics)
  footer?: ReactNode; // dòng dưới biểu đồ (VD link từ landing sang /analytics)
}) {
  const info = RATE_INFO[rate];
  const rateName = info.label.toLowerCase();
  const fmt = (v: number) => pct(v, info.digits);
  const topic = data.topics.find((t) => t.id === topicId) ?? null;
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

  // Bài không có topic (unclustered / chưa gom cụm) → chỉ còn tập "cả kênh", dù nút trước đó đang ở "Same topic"
  const isChannel = set === "channel" || topic === null;
  const { rates, stats } = isChannel ? data.channel.byRate[rate] : topic.byRate[rate];
  const { below, others: otherCount, share } = rankAmongOthers(rates, value);
  // Làm tròn xuống ra 0 dù có bài thấp hơn → "<1%" (K4), không "0%"
  const shareText = below > 0 && share === 0 ? "<1" : `${share}`;
  // Bài khác có cùng tỉ lệ (share / conversation rate có nhiều bài 0%): không tính là "thấp hơn"
  const ties = rates.filter((v) => v === value).length - (rates.includes(value) ? 1 : 0);
  const above = value > stats.median;
  const atMedian = value === stats.median;
  const channelAbove = value > data.channel.byRate[rate].stats.median;
  // Trục chung cho 2 tập so (đổi tập không đổi thước): engagement giữ trục của landing; share / conversation (thường
  // < 1%) lấy bước nhỏ hơn
  const axis =
    rate === "engagement"
      ? { max: data.axisMax, ticks: ticks(data.axisMax), decimals: 0 }
      : rateAxis(data.channel.byRate[rate].rates);
  const axisMax = axis.max;

  const gap = Math.max(6.5, 9 * Math.min(1, width / DESIGN_WIDTH));
  // Nhiều bài cùng một giá trị (share / conversation rate: hàng chục bài 0%) → cột chấm cao hơn khung. Thy 2026-11-02
  // chọn gộp: cột vẽ gọn trong khung, kèm nhãn chữ đếm đúng số bài (chiều cao biểu đồ giữ nguyên giữa 3 tỉ lệ). Cột vừa
  // khung (≤ `fits` chấm) vẽ như cũ; cột gộp chừa 1 hàng nhãn phía trên dưới nhãn median
  const fits = 2 * Math.floor((CENTRE_Y - 28) / gap) + 1;
  const tally = new Map<number, number>();
  for (const v of rates) tally.set(v, (tally.get(v) ?? 0) + 1);
  const crowded = [...tally].filter(([, n]) => n > fits).map(([v, n]) => ({ value: v, n }));
  const cap = crowded.length > 0 ? 2 * Math.floor((CENTRE_Y - 48) / gap) + 1 : fits;
  const ordered = withSelectedLast(rates, value);
  const kept = new Map<number, number>();
  const drawn = ordered.filter((v, i) => {
    if (i === ordered.length - 1) return true; // bài được chọn luôn được vẽ
    // Chỉ cắt cột thật sự đông (> `fits`, có nhãn đếm) — cột vừa khung giữ đủ chấm (code-reviewer 2026-11-02)
    if (tally.get(v)! <= fits) return true;
    const k = (kept.get(v) ?? 0) + 1;
    kept.set(v, k);
    return k <= cap - (v === value ? 1 : 0); // chừa 1 chỗ cho bài được chọn nếu nó cùng giá trị
  });
  const placed = swarm(drawn, {
    width,
    axisMax,
    cy: CENTRE_Y,
    step: gap,
    minDist: gap,
    // Có cột gộp: mọi chấm ở trong khung (`fits` vị trí dọc); hết chỗ thì về tâm thay vì tràn khung
    tries: crowded.length > 0 ? fits : 40,
  });
  const selectedIndex = drawn.length - 1;
  const selectedDot = placed.find((dot) => dot.index === selectedIndex)!;
  const selectedX = selectedDot.x;

  // Màn hẹp (biểu đồ rộng hơn khung): mở vùng cuộn ở chỗ chấm được chọn, để câu trả lời và bằng chứng cùng thấy được
  // (ux-reviewer PR 2b, L2/C1). Cuộn tức thời, không hoạt cảnh (hợp reduced-motion)
  useEffect(() => {
    const el = boxRef.current;
    if (!el || el.scrollWidth <= el.clientWidth) return;
    // Căn giữa giữa median và chấm được chọn (câu trả lời + mốc so cùng thấy), nhưng không cuộn quá mép trái nhãn
    // median (~60px). Ưu tiên chấm + nhãn của nó (~90px) luôn trong khung (code-reviewer: bài xa median thì median nhường)
    const medianX = (stats.median / axisMax) * el.scrollWidth;
    const selectedPx = (selectedX / width) * el.scrollWidth;
    const preferred = Math.min((selectedPx + medianX) / 2 - el.clientWidth / 2, medianX - 60);
    // Kẹp 2 phía: bài xa median về bên phải hay bên trái thì chấm + nhãn vẫn trong khung
    el.scrollLeft = Math.min(Math.max(0, preferred, selectedPx + 90 - el.clientWidth), Math.max(0, selectedPx - 90));
  }, [selectedX, width, set, stats.median, axisMax]);
  const others = placed.filter((dot) => dot.index !== selectedIndex);

  // Câu trả lời sinh từ dữ liệu (handoff §0 loại C), không viết cứng kết luận
  // "do better than usual" = cao hơn median (đúng phép đo, Thy duyệt 2026-10-08) — không có ngưỡng "strong"
  // Tập mang cờ insufficient_data: chỉ mô tả thứ hạng, không Yes/Not (UI-L20260903-small-n-flag)
  const flagged = stats.insufficient_data;
  const unitWord = otherCount === 1 ? "content unit" : "content units";
  const tieText = ties > 0 ? `, tied with ${ties} other ${ties === 1 ? "content unit" : "content units"}` : "";
  const answer = isChannel
    ? otherCount === 0
      ? "It is the only content unit with recorded views so far."
      : flagged
        ? `Its ${rateName} is higher than ${shareText}% of the channel's other content units; too few content units to interpret.`
        : atMedian
          ? "About usual: it sits at the channel median."
          : above
            ? below === otherCount
              ? `Yes. Its ${rateName} is the highest in the channel.`
              : `Yes. Its ${rateName} is higher than ${shareText}% of the channel's other content units.`
            : below === 0
              ? `Not this time. Its ${rateName} is the lowest in the channel${tieText}.`
              : shareText === "<1"
                ? // "higher than only <1%" đọc vụng → đếm (copy-reviewer 2026-11-02)
                  `Not this time. Its ${rateName} is higher than only ${below} of the channel's ${count(otherCount)} other content units.`
                : `Not this time. Its ${rateName} is higher than only ${shareText}% of the channel's other content units.`
    : otherCount === 0
      ? "It is the only content unit with recorded views in its topic."
      : flagged
        ? `Within its topic: higher than ${below} of the other ${otherCount} "${topic.name}" ${unitWord}; too few content units to interpret.`
        : atMedian
          ? "About usual within its topic: it sits at the topic median."
          : above
            ? `${channelAbove && !data.channel.byRate[rate].stats.insufficient_data ? "Yes, within its topic too" : "Within its topic, yes"}: ${
                below === otherCount
                  ? `the highest of the ${otherCount + 1} "${topic.name}" content units.`
                  : `higher than ${below} of the other ${otherCount} "${topic.name}" ${unitWord}.`
              }`
            : below === 0
              ? `Not within its topic: its ${rateName} is the lowest of the ${otherCount + 1} "${topic.name}" content units${tieText}.`
              : `Not within its topic: higher than ${below} of the other ${otherCount} "${topic.name}" ${unitWord}.`;
  const footNote = isChannel
    ? data.channel.excluded > 0
      ? `${data.channel.excluded} of ${count(data.channel.total)} excluded: no views recorded.`
      : null
    : `${topic.name} (named by Claude) · ${stats.n} ${stats.n === 1 ? "content unit" : "content units"} with recorded views${
        stats.insufficient_data ? " · too few content units to interpret" : ""
      }${topic.excluded > 0 ? ` · ${topic.excluded} excluded: no views recorded` : ""}.`;

  // Key numbers (K1–K5): tỉ lệ của bài → thứ hạng (phần của "các bài khác", thanh tỉ lệ) → median + IQR + n một dòng
  const setName = isChannel ? "all content units" : `"${topic.name}"`;
  // Số bài 0% của tập đang vẽ — Limits nói số thật, không "many" (copy-reviewer: conversation chỉ 10/163 bài 0 reply)
  const zeros = rates.filter((v) => v === 0).length;
  const numbers: KeyNumber[] = [
    { value: fmt(value), label: `${info.label} of this content unit`, note: `${info.formula}, on its opening post.` },
    ...(otherCount > 0
      ? [
          {
            value: `${count(below)} of ${count(otherCount)}`,
            label: isChannel ? "other content units with a lower rate" : `other "${topic.name}" content units with a lower rate`,
            share: { part: below, whole: otherCount, of: `the ${count(otherCount)} others` },
          },
        ]
      : []),
    {
      value: hasPosts(stats) ? fmt(stats.median) : "—",
      label: `median ${rateName}, ${setName}`,
      note: rateNote(stats, info.digits, "No content unit has recorded views yet."),
    },
  ];
  // aria-live: đổi bài / tỉ lệ / tập so thì trình đọc màn hình đọc câu trả lời mới (ux-reviewer 2026-11-02, A2)
  const answerText = <span aria-live="polite">{answer}</span>;

  return (
    <>
      {keyNumbers ? (
        // Cột trái có ý chính cách đọc câu trả lời, để không bỏ trống dưới khung ANSWER cạnh hộp số (L5)
        <AnswerRow
          answer={answerText}
          points={[
            topic === null
              ? "Compared with **all content units** with recorded views (it has no topic); the buttons below switch to another rate."
              : isChannel
                ? "Compared with **all content units** with recorded views; the buttons below switch to its own topic or to another rate."
                : `Compared with the other content units of **"${topic.name}"**; the buttons below switch back to the whole channel or to another rate.`,
            `"Yes" means its ${rateName} is **above the median** of that set.`,
            "The rank counts the others with a **strictly lower** rate; equal rates do not count.",
            "A rank is **described, not tested**: it does not say why this content unit did well or badly.",
          ]}
          keyNumbers={numbers}
        />
      ) : (
        <Answer>{answerText}</Answer>
      )}

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className={TYPE.label}>Compare with</span>
            {/* Nút chung của mọi trang (C2/C4: 44px, aria-pressed); không có topic → chỉ còn 1 lựa chọn */}
            <ToggleGroup
              label="Comparison set"
              options={[
                { key: "channel", label: `All content units · ${count(data.channel.byRate[rate].stats.n)}` },
                ...(topic ? [{ key: "topic" as const, label: `Same topic · ${count(topic.byRate[rate].stats.n)}` }] : []),
              ]}
              value={isChannel ? "channel" : "topic"}
              onChange={setSet}
            />
          </div>
          {controls}
        </div>
        {topic === null ? (
          <p className={`m-0 ${TYPE.note}`}>
            This content unit has no topic in the latest clustering run, so it is compared with the whole channel only.
          </p>
        ) : null}

        {/* Dưới 720px biểu đồ cuộn ngang trong vùng có focus bàn phím (A1: vùng cuộn dùng được bằng phím mũi tên) */}
        <div
          ref={boxRef}
          tabIndex={0}
          role="region"
          aria-label={`${info.label} of every content unit, with this one highlighted`}
          className="overflow-x-auto rounded-md px-4"
        >
          <div className="relative h-[250px] min-w-[720px] tabular-nums">
            {hasPosts(stats) ? (
              <>
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
                  median {fmt(stats.median)}
                </span>
                <span
                  className={`absolute bottom-10 whitespace-nowrap pl-2 ${TYPE.mono} text-text-secondary`}
                  style={{ left: axisPct(stats.median, axisMax) }}
                >
                  middle half {stats.iqr_low.toFixed(info.digits)}–{fmt(stats.iqr_high)}
                </span>
              </>
            ) : null}
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
            {/* Nhãn đếm của cột gộp: hàng riêng ngay dưới nhãn median, căn trái từ cột (gần mép phải thì căn phải) */}
            {crowded.map((col) => {
              const x = (col.value / axisMax) * width;
              return (
                <span
                  key={col.value}
                  className={`absolute top-6 z-10 whitespace-nowrap rounded bg-bg-card/90 px-1 ${TYPE.mono} font-medium text-text-primary ${
                    x > width - 2 * LABEL_HALF ? "-translate-x-full" : "-translate-x-1"
                  }`}
                  style={{ left: `${(x / width) * 100}%` }}
                >
                  {count(col.n)} content units at {fmt(col.value)}
                </span>
              );
            })}
            <div
              aria-hidden="true"
              className="absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-amber-600 shadow-[0_0_0_1px_var(--amber-600)]"
              style={{ left: `${(selectedDot.x / width) * 100}%`, top: selectedDot.y }}
            />
            {/* Nền trắng mờ: chấm của cột cao không đè lên chữ (ux-reviewer 2026-11-02) */}
            {/* Kẹp theo mép: chấm gần mép trái/phải thì chú thích căn trái/phải từ chấm, không bị cắt (ux-reviewer
                2026-11-02: share / conversation rate gần 0%) */}
            <div
              className={`absolute z-10 flex flex-col gap-0.5 whitespace-nowrap rounded bg-bg-card/90 px-1 ${
                selectedX < LABEL_HALF
                  ? "-translate-x-2 items-start"
                  : selectedX > width - LABEL_HALF
                    ? "-translate-x-[calc(100%-8px)] items-end"
                    : "-translate-x-1/2 items-center"
              }`}
              // Chấm nằm cao (đỉnh cột gộp, nhất là ở 375px) → chú thích xuống dưới chấm, không đè hàng nhãn median
              // (~24px) và hàng nhãn đếm của cột gộp (~48px) ở trên cùng (ux-reviewer 2026-11-02)
              style={{
                left: `${(selectedDot.x / width) * 100}%`,
                top: selectedDot.y - 52 < (crowded.length > 0 ? 48 : 24) ? selectedDot.y + 12 : selectedDot.y - 52,
              }}
            >
              <span className={`${TYPE.cell} font-semibold text-amber-700`}>This content unit · {fmt(value)}</span>
              {otherCount > 0 ? (
                <span className={`${TYPE.label} text-text-secondary`}>
                  higher than {below} of the other {count(otherCount)}
                </span>
              ) : null}
            </div>
            <div className="absolute inset-x-0 bottom-[22px] h-px bg-rule" />
            {/* Vạch đầu căn trái, vạch cuối căn phải: nhãn 2 chữ số thập phân không tràn khỏi vùng vẽ */}
            {axis.ticks.map((tick, i) => (
              <span
                key={tick}
                // căn phải chỉ khi vạch nằm đúng mép phải (trục `rateAxis`); trục engagement có vạch nguyên < mép
                className={`absolute bottom-0 ${
                  i === 0 ? "" : tick >= axisMax ? "-translate-x-full" : "-translate-x-1/2"
                } ${TYPE.mono} text-text-muted`}
                style={{ left: axisPct(tick, axisMax) }}
              >
                {tick.toFixed(axis.decimals)}%
              </span>
            ))}
          </div>
        </div>
        {footNote ? <p className={`m-0 ${TYPE.note}`}>{footNote}</p> : null}
        {footer}
      </div>

      <MethodSection
        steps={[
          {
            title: info.label,
            plain: "Interactions are counted on the content unit's opening post, per 100 views of that post, so content units with few and many views sit on one scale.",
            formula: `${rateName} = ${info.formula}`,
          },
          {
            title: "Dots",
            plain: `Each dot is one content unit with recorded views${isChannel ? "" : " in the same topic"}, stacked so none overlap; the highlighted dot is this one.${
              crowded.length > 0
                ? " A stack too tall for the chart is cut to fit, and a label gives its full count."
                : ""
            }`,
          },
          {
            title: "Median and middle half",
            plain: "The median is the rate of the middle content unit once they are sorted by rate. The middle half runs from the 25th to the 75th percentile (Q₁ to Q₃); the grey band shows it.",
            formula: "middle half = [ Q_1 , Q_3 ]",
          },
          {
            title: "Rank",
            plain: "Yes means its rate is above the median. The percentage is the share of the other content units with a strictly lower rate (equal rates do not count as lower), rounded down. A share above 0 but below 1% shows as <1%.",
            formula: "share = ⌊ below × 100 ÷ others ⌋",
          },
        ]}
        limits={[
          "Rates use the **latest counts**, re-read every 4 hours while the collecting laptop is awake, so they are usually less than a day old.",
          "Newer content units have had **less time** to collect views and interactions.",
          rate === "engagement" || zeros === 0
            ? null
            : `${count(zeros)} of ${count(rates.length)} content units in this set have **no ${rate === "share" ? "reposts or quotes" : "replies"}** at all, so they tie at 0%; tied content units do not count as lower.`,
          "Interactions on the **follow-up parts are not counted**; only the opening post's are.",
          "One content unit is **described, not tested**: its rank does not say why it did well or badly.",
          `Content units without recorded views are left out${data.summary.latest_snapshot_at ? `; data as of ${dayMonthYear(data.summary.latest_snapshot_at)}` : ""}.`,
        ]}
      />
    </>
  );
}
