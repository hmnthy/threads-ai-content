"use client";

import { useMemo, useState, type CSSProperties } from "react";
import { CaretDown } from "@phosphor-icons/react";
import { AnswerRow, MethodSection, SubSection, ToggleGroup, TYPE } from "@/components/AppBlock";
import { WEEKDAY_LABELS, type DistributionStats, type TimezoneEngagement } from "@/lib/api";
import {
  Iqr,
  NO_POSTS,
  TOO_FEW_POSTS,
  distributionCaptionText,
  formatIqrRange,
} from "@/components/DistributionCaption";

// Heatmap giờ/thứ đăng — design-system.md §9: "Giờ/thứ đăng hiệu quả → Heatmap, thang
// tuần tự 1 hue (amber)". Mỗi ô ghi n (Narrative Layering tầng 3): ô thiếu dữ liệu
// (`insufficient_data`, n < MIN_N_PER_BUCKET ở backend) KHÔNG được tô màu theo giá trị
// — gạch chéo + chữ mờ, để người xem không đọc "giờ tốt nhất" từ 1-2 bài.
//
// Màu = color-mix giữa 2 token amber (không hex rời). Trần 65% amber-700: tính trên
// OKLab, ô đậm nhất có luminance ~0.26 → chữ --text-primary vẫn đạt ~4.9:1, nên mọi
// ô dùng chung 1 màu chữ, không phải đổi trắng/đen theo nền.
const MIX_MIN = 8;
const MIX_MAX = 65;

const CLOCKS = [
  { timezone: "Europe/Paris", label: "Paris time" },
  { timezone: "Asia/Ho_Chi_Minh", label: "Vietnam time" },
] as const;

interface Cell {
  key: string;
  label: string; // nhãn trục: "08" hoặc "Mon"
  description: string; // câu đầy đủ cho tooltip / aria
  stats: DistributionStats | null;
}

function pct(value: number): string {
  return `${value.toFixed(2)}%`;
}

function describe(prefix: string, stats: DistributionStats | null): string {
  // n chỉ đếm content unit CÓ views: ô n = 0 vẫn có thể có bài đăng giờ đó mà chưa ghi được views (copy-reviewer)
  if (stats === null || stats.n === 0) return `${prefix} · ${NO_POSTS}`;
  return `${prefix} · median ${pct(stats.median)} · ${distributionCaptionText(stats)}`;
}

// Thang màu chỉ trải trên các ô ĐỦ dữ liệu — ô thiếu dữ liệu không được kéo giãn thang.
function mixFor(stats: DistributionStats | null, lo: number, hi: number): number | null {
  if (stats === null || stats.n === 0 || stats.insufficient_data) return null;
  if (hi <= lo) return (MIX_MIN + MIX_MAX) / 2;
  return MIX_MIN + ((stats.median - lo) / (hi - lo)) * (MIX_MAX - MIX_MIN);
}

function cellStyle(mix: number | null, hasPosts: boolean): CSSProperties {
  if (mix !== null) {
    return { background: `color-mix(in oklab, var(--amber-700) ${mix.toFixed(1)}%, var(--amber-soft))` };
  }
  if (hasPosts) {
    // Gạch chéo 45° = "có bài nhưng quá ít để đọc" — không mã hoá giá trị bằng màu
    return {
      background:
        "repeating-linear-gradient(45deg, var(--bg-surface) 0 4px, var(--bg-card) 4px 8px)",
    };
  }
  return { background: "var(--bg-sunken)" };
}

function HeatRow({
  title,
  cells,
  columnsClass,
  lo,
  hi,
  active,
  onActivate,
}: {
  title: string;
  cells: Cell[];
  columnsClass: string;
  lo: number;
  hi: number;
  active: string | null;
  onActivate: (cell: Cell | null) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[12px] font-semibold text-text-secondary">{title}</span>
      <div className={`grid gap-[2px] ${columnsClass}`} role="list" aria-label={title}>
        {cells.map((cell) => {
          const stats = cell.stats;
          const hasPosts = stats !== null && stats.n > 0;
          const readable = hasPosts && !stats.insufficient_data;
          return (
            <div
              key={cell.key}
              role="listitem"
              tabIndex={0}
              aria-label={cell.description}
              onMouseEnter={() => onActivate(cell)}
              onMouseLeave={() => onActivate(null)}
              onFocus={() => onActivate(cell)}
              onBlur={() => onActivate(null)}
              className={`flex min-h-[60px] flex-col items-center justify-center rounded-[4px] border px-0.5 py-1 outline-none focus-visible:ring-2 focus-visible:ring-amber-600 ${
                active === cell.key ? "border-text-primary" : "border-border-hairline"
              }`}
              style={cellStyle(mixFor(stats, lo, hi), hasPosts)}
            >
              {/* Chữ trong ô theo thang chung (§3: nhỏ nhất 12px; số mono 12.5px) — ô đủ rộng nhờ 6 cột ở màn hẹp */}
              <span className={`font-mono text-[12.5px] ${readable ? "text-text-primary" : "text-text-muted"}`}>{cell.label}</span>
              <span
                className={`font-mono text-[12.5px] tabular-nums ${
                  readable ? "font-semibold text-text-primary" : "text-text-muted"
                }`}
              >
                {readable ? stats.median.toFixed(1) : "–"}
              </span>
              <span className={`font-mono text-[12.5px] tabular-nums ${readable ? "text-text-primary" : "text-text-muted"}`}>
                {hasPosts ? `n ${stats.n}` : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Thân khối 02 của /analytics (khung + tiêu đề h2 do `Section` của AnalyticsBreakdown giữ): câu trả lời → ý chính →
// heatmap (bằng chứng) → chú giải → bảng → "Method and limits" mở sẵn
export function PostingTimeHeatmap({
  timezones,
  excludedNoViews,
  totalUnits,
  minPosts,
}: {
  timezones: TimezoneEngagement[];
  // ADR-0011: bài views = 0 bị loại khỏi mọi ô — phải nói ra, không loại ngầm
  excludedNoViews: number;
  totalUnits: number; // mẫu số của dòng loại: content unit đo được + bị loại (UI-0011-excluded)
  // ngưỡng mẫu nhỏ của backend (MIN_N_PER_BUCKET, qua /pipeline/summary) — UI ghi số này, không tự đặt; null khi không
  // đọc được summary → câu chữ bỏ con số (cờ insufficient_data của từng ô vẫn từ backend)
  minPosts: number | null;
}) {
  const available = CLOCKS.filter((clock) => timezones.some((tz) => tz.timezone === clock.timezone));
  const [clock, setClock] = useState<string>(available[0]?.timezone ?? "");
  const [activeCell, setActiveCell] = useState<Cell | null>(null);

  const tz = timezones.find((item) => item.timezone === clock);
  const clockLabel = CLOCKS.find((item) => item.timezone === clock)?.label ?? clock;

  const { hourCells, weekdayCells, lo, hi } = useMemo(() => {
    const hours: Cell[] = Array.from({ length: 24 }, (_, hour) => {
      const stats = tz?.by_hour.find((b) => b.hour === hour)?.stats ?? null;
      const label = hour.toString().padStart(2, "0");
      return { key: `h${hour}`, label, description: describe(`${label}:00 ${clockLabel}`, stats), stats };
    });
    const days: Cell[] = Array.from({ length: 7 }, (_, weekday) => {
      const stats = tz?.by_weekday.find((b) => b.weekday === weekday)?.stats ?? null;
      const label = WEEKDAY_LABELS[weekday];
      return { key: `d${weekday}`, label, description: describe(`${label} (${clockLabel})`, stats), stats };
    });
    // 1 thang chung cho cả 2 hàng (giờ + thứ) để 1 chú giải màu đọc được cho cả hai
    const readable = (cells: Cell[]) =>
      cells.flatMap((c) => (c.stats && c.stats.n > 0 && !c.stats.insufficient_data ? [c.stats.median] : []));
    const all = [...readable(hours), ...readable(days)];
    return {
      hourCells: hours,
      weekdayCells: days,
      lo: all.length > 0 ? Math.min(...all) : 0,
      hi: all.length > 0 ? Math.max(...all) : 0,
    };
  }, [tz, clockLabel]);

  if (tz === undefined) {
    return <p className={`m-0 ${TYPE.body}`}>No posting-time breakdown yet: it appears once views are recorded.</p>;
  }

  const tableRows = [...hourCells, ...weekdayCells].filter((c) => c.stats !== null && c.stats.n > 0);
  // Không ô nào đủ dữ liệu → không có thang màu để chú giải; lo == hi → chỉ 1 mức màu
  const hasScale = [...hourCells, ...weekdayCells].some(
    (c) => c.stats !== null && c.stats.n > 0 && !c.stats.insufficient_data,
  );

  //  : bất đẳng thức không bị ngắt dòng giữa chừng ("(n <" / "5)") ở màn hẹp (ux-reviewer 2026-11-02)
  const tooFew = minPosts === null ? "too few content units" : `too few content units (n < ${minPosts})`;
  // Câu trả lời mô tả (Thy 2026-10-31): khoảng median của các ô đọc được theo giờ và theo thứ, trên đồng hồ đang chọn —
  // không nêu tên ô cao nhất (tránh đọc thành "giờ tốt nhất"), kèm "chưa kiểm định" ngay trong câu
  // Khoảng median của các ô đọc được; nhánh riêng cho 1 ô và cho min = max (code-reviewer: không "from X to X")
  const range = (cells: Cell[]) => {
    const medians = cells.flatMap((c) => (c.stats && c.stats.n > 0 && !c.stats.insufficient_data ? [c.stats.median] : []));
    if (medians.length === 0) return null;
    const lo = Math.min(...medians);
    const hi = Math.max(...medians);
    return { count: medians.length, lo: pct(lo), hi: pct(hi), same: pct(lo) === pct(hi) };
  };
  const hourRange = range(hourCells);
  const dayRange = range(weekdayCells);
  // Ngưỡng nói bằng chữ ngay trong câu (copy-reviewer lượt 3: "readable" dùng trước khi định nghĩa); câu ngắn, 1 ý
  const enough = minPosts === null ? "enough content units" : `at least ${minPosts} content units`;
  const clockName = clockLabel.replace(/ time$/, "");
  const hourSentence = !hourRange
    ? null
    : hourRange.count === 1
      ? `On the ${clockName} clock, only one hour has ${enough}; its median engagement rate is ${hourRange.lo}.`
      : hourRange.same
        ? `On the ${clockName} clock, the ${hourRange.count} hours with ${enough} all have a median engagement rate of ${hourRange.lo}.`
        : `On the ${clockName} clock, hours with ${enough} have median engagement rates from ${hourRange.lo} to ${hourRange.hi}.`;
  const daySentence = !dayRange
    ? null
    : dayRange.count === 1
      ? `Only one weekday has ${enough}; its median is ${dayRange.lo}.`
      : dayRange.same
        ? `The ${dayRange.count} weekdays with ${enough} all have a median of ${dayRange.lo}.`
        : `Across weekdays with ${enough}, the range is ${dayRange.lo} to ${dayRange.hi}.`;
  const hasGap = [hourRange, dayRange].some((r) => r !== null && r.count > 1 && !r.same);
  const answer =
    hourRange === null && dayRange === null
      ? "No hour or weekday has enough content units to read yet."
      : [hourSentence, daySentence, hasGap ? "None of these differences has been tested." : null].filter(Boolean).join(" ");
  return (
    <>
      <AnswerRow
        answer={answer}
        points={[
          "Each cell shows the **median engagement rate** (%) of the content units published in that hour or on that weekday, rounded to one decimal.",
          "Below it, **n** is how many content units that median rests on; the table gives two decimals.",
          `Cells with ${tooFew} are **hatched** instead of coloured; their median appears only in the hover text and the table below.`,
          // Chuỗi chuẩn UI-0011-excluded
          excludedNoViews > 0 ? `${excludedNoViews} of ${totalUnits} excluded: no views recorded; they are in no cell.` : null,
        ]}
      />
      <SubSection
        title={`Engagement rate by posting time (${clockLabel})`}
        note="Switch the clock to read the same content units in the other time zone."
        action={
          <ToggleGroup
            label="Clock"
            options={available.map((item) => ({ key: item.timezone, label: item.label }))}
            value={clock}
            onChange={setClock}
          />
        }
      >

      <HeatRow
        title={`Hour of day (${clockLabel})`}
        cells={hourCells}
        columnsClass="grid-cols-[repeat(6,minmax(0,1fr))] sm:grid-cols-[repeat(12,minmax(0,1fr))] lg:grid-cols-[repeat(24,minmax(0,1fr))]"
        lo={lo}
        hi={hi}
        active={activeCell?.key ?? null}
        onActivate={setActiveCell}
      />
      <HeatRow
        title={`Weekday (${clockLabel})`}
        cells={weekdayCells}
        columnsClass="grid-cols-[repeat(7,minmax(0,1fr))]"
        lo={lo}
        hi={hi}
        active={activeCell?.key ?? null}
        onActivate={setActiveCell}
      />

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[12px] text-text-secondary">
        {!hasScale ? (
          <span>No hour or weekday has enough content units to read yet.</span>
        ) : hi <= lo ? (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span
              aria-hidden="true"
              className="h-3 w-5 rounded-[3px] border border-border-hairline"
              style={cellStyle((MIX_MIN + MIX_MAX) / 2, true)}
            />
            <span className="font-mono tabular-nums">{pct(lo)}</span>
            <span>median engagement rate (all readable cells)</span>
          </div>
        ) : (
        // flex-wrap: ở 320px chữ "median engagement rate" xuống dòng thay vì tràn mép (ux-reviewer 2026-11-02)
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono tabular-nums">{pct(lo)}</span>
          <span
            aria-hidden="true"
            className="h-2.5 w-28 rounded-full border border-border-hairline"
            style={{
              background: `linear-gradient(90deg, color-mix(in oklab, var(--amber-700) ${MIX_MIN}%, var(--amber-soft)), color-mix(in oklab, var(--amber-700) ${MIX_MAX}%, var(--amber-soft)))`,
            }}
          />
          <span className="font-mono tabular-nums">{pct(hi)}</span>
          <span>median engagement rate</span>
        </div>
        )}
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="h-3 w-5 rounded-[3px] border border-border-hairline" style={cellStyle(null, true)} />
          <span>{tooFew}: hatched, not coloured</span>
        </div>
        {/* Ô không có content unit nào: không sọc, không n (ux-reviewer lượt 4 N3 — chú giải phải nói đủ mọi kiểu ô) */}
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="h-3 w-5 rounded-[3px] border border-border-hairline" style={cellStyle(null, false)} />
          <span>no n: {NO_POSTS} in that hour or weekday</span>
        </div>
      </div>

      {/* Câu chữ: TYPE.note (sans) — mono chỉ cho công thức, ID, số (ux-reviewer S9) */}
      <p className={`m-0 min-h-[20px] ${TYPE.note} text-text-primary`} aria-live="polite">
        {activeCell?.description ?? "Hover or focus a cell for its median, IQR and n."}
      </p>

      {/* Nút mở bảng trông rõ là nút, cùng kiểu nút "Method and limits" (C3): viền + nền + chevron, vùng chạm 44px */}
      <details className="group text-[13px]">
        <summary className="inline-flex min-h-[44px] cursor-pointer list-none items-center gap-2 rounded-full border border-border-hairline bg-bg-surface px-4 text-[13px] font-semibold text-text-primary hover:border-amber-600 hover:text-amber-700 [&::-webkit-details-marker]:hidden">
          <CaretDown size={16} aria-hidden="true" className="transition-transform duration-150 group-open:rotate-180" />
          Show as table
        </summary>
        <div className="mt-3 overflow-x-auto" tabIndex={0} role="region" aria-label="Median engagement rate by bucket, as a table">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="text-left">
                <th scope="col" className={`py-1.5 pr-4 ${TYPE.th}`}>Hour or weekday ({clockLabel})</th>
                <th scope="col" className={`py-1.5 pr-4 text-right ${TYPE.th}`}>Median</th>
                <th scope="col" className={`py-1.5 pr-4 text-right ${TYPE.th}`}>
                  <Iqr />
                </th>
                <th scope="col" className={`py-1.5 text-right ${TYPE.th}`}>n</th>
              </tr>
            </thead>
            <tbody className="font-mono text-[12.5px] tabular-nums">
              {tableRows.map((cell) => (
                <tr key={cell.key} className="border-t border-border-hairline hover:bg-bg-surface">
                  <td className="py-1.5 pr-4">{cell.key.startsWith("h") ? `${cell.label}:00` : cell.label}</td>
                  <td className="py-1.5 pr-4 text-right">{pct(cell.stats!.median)}</td>
                  <td className="py-1.5 pr-4 text-right">
                    {formatIqrRange(cell.stats!)}
                  </td>
                  <td className="py-1.5 text-right">
                    {cell.stats!.n}
                    {cell.stats!.insufficient_data ? ` · ${TOO_FEW_POSTS}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      </SubSection>
      <MethodSection
        steps={[
          {
            title: "Cell",
            plain: "Each content unit goes to the hour and the weekday its opening post was published, on the chosen clock.",
          },
          {
            title: "Median per cell",
            plain: "The cell shows the median engagement rate of its content units, with the middle half (IQR) and n in the hover text and the table.",
            formula: [
              "engagement rate = (likes + replies + reposts + quotes) ÷ views × 100",
              "cell value = median{ engagement rate of the cell's content units }",
              "n = their count",
            ],
          },
          {
            title: "Readable cells",
            plain: `A cell is readable (coloured, and counted in the ranges at the top of this section) only when it rests on ${minPosts === null ? "enough" : `at least ${minPosts}`} content units, the same minimum every comparison on this dashboard uses. The colour scale runs only across those cells.`,
            // 3 nhánh khớp `cellStyle` + chú giải: ô n = 0 nền `--bg-sunken` (gần trắng — "plain", không gọi "grey"
            // vì ô sọc mới trông xám), không sọc, không ghi n ("no n")
            formula:
              minPosts === null
                ? undefined
                : [`n ≥ ${minPosts} → coloured`, `1 ≤ n < ${minPosts} → hatched`, "n = 0 → plain, no n"],
          },
        ]}
        limits={[
          "**Descriptive only**: differences between hours or weekdays have not been tested.",
          "Posting time overlaps with topic, so a cell can reflect what was posted rather than when.",
          "No cell is a recommended time to post.",
        ]}
      />
    </>
  );
}
