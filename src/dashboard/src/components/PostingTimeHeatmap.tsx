"use client";

import { useMemo, useState, type CSSProperties } from "react";
import { WEEKDAY_LABELS, type DistributionStats, type TimezoneEngagement } from "@/lib/api";
import {
  Iqr,
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
  if (stats === null || stats.n === 0) return `${prefix} · no posts`;
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
      <span className="text-xs font-medium text-text-secondary">{title}</span>
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
              className={`flex min-h-[52px] flex-col items-center justify-center rounded-[4px] border px-0.5 py-1 outline-none focus-visible:ring-2 focus-visible:ring-amber-600 ${
                active === cell.key ? "border-text-primary" : "border-border-hairline"
              }`}
              style={cellStyle(mixFor(stats, lo, hi), hasPosts)}
            >
              <span className={`font-mono text-[10px] ${readable ? "text-text-primary" : "text-text-muted"}`}>{cell.label}</span>
              <span
                className={`font-mono text-[11px] tabular-nums ${
                  readable ? "font-semibold text-text-primary" : "text-text-muted"
                }`}
              >
                {readable ? stats.median.toFixed(1) : "–"}
              </span>
              <span className={`font-mono text-[10px] tabular-nums ${readable ? "text-text-primary" : "text-text-muted"}`}>
                {hasPosts ? `n ${stats.n}` : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PostingTimeHeatmap({
  timezones,
  excludedNoViews,
}: {
  timezones: TimezoneEngagement[];
  // ADR-0011: bài views = 0 bị loại khỏi mọi ô — phải nói ra, không loại ngầm
  excludedNoViews: number;
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
    return (
      <section className="rounded-xl border border-border-hairline bg-bg-card p-5 text-sm text-text-secondary">
        No posting-time breakdown yet — it appears once posts have insight snapshots.
      </section>
    );
  }

  const tableRows = [...hourCells, ...weekdayCells].filter((c) => c.stats !== null && c.stats.n > 0);
  // Không ô nào đủ dữ liệu → không có thang màu để chú giải; lo == hi → chỉ 1 mức màu
  const hasScale = [...hourCells, ...weekdayCells].some(
    (c) => c.stats !== null && c.stats.n > 0 && !c.stats.insufficient_data,
  );

  return (
    <section className="flex flex-col gap-4 rounded-xl border border-border-hairline bg-bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-[720px] flex-col gap-1">
          <h2 className="text-[15px] font-semibold text-text-primary">
            Median engagement rate by posting hour and weekday
          </h2>
          <p className="text-[13px] leading-snug text-text-secondary">
            The same posts, placed on a Paris or a Vietnam clock. Each cell shows the median rate (%) and
            how many posts it rests on. Hatched cells hold too few posts to interpret; their median is only in the table below.
          </p>
        </div>
        <div className="flex gap-2" role="group" aria-label="Clock">
          {available.map((item) => (
            <button
              key={item.timezone}
              type="button"
              aria-pressed={clock === item.timezone}
              onClick={() => setClock(item.timezone)}
              className={`min-h-[36px] rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                clock === item.timezone
                  ? "bg-amber-600 text-white"
                  : "text-text-secondary hover:bg-bg-surface hover:text-text-primary"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <HeatRow
        title={`Hour of day (${clockLabel})`}
        cells={hourCells}
        columnsClass="grid-cols-[repeat(12,minmax(0,1fr))] lg:grid-cols-[repeat(24,minmax(0,1fr))]"
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

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-text-secondary">
        {!hasScale ? (
          <span>No hour or weekday has enough posts to read yet.</span>
        ) : hi <= lo ? (
          <div className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="h-3 w-5 rounded-[3px] border border-border-hairline"
              style={cellStyle((MIX_MIN + MIX_MAX) / 2, true)}
            />
            <span className="font-mono tabular-nums">{pct(lo)}</span>
            <span>median engagement rate (all readable cells)</span>
          </div>
        ) : (
        <div className="flex items-center gap-2">
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
          <span>too few posts to interpret</span>
        </div>
      </div>

      <p className="min-h-[20px] font-mono text-xs tabular-nums text-text-primary" aria-live="polite">
        {activeCell?.description ?? "Hover or focus a cell for median, IQR and n."}
      </p>

      <p className="text-[13px] leading-snug text-text-muted">
        {excludedNoViews > 0
          ? `${excludedNoViews} posts without views are left out of every cell. `
          : ""}
        Descriptive only. Differences between hours have not been tested for significance, and posting time
        overlaps with topic — so this is not a recommended time to post.
      </p>

      <details className="text-sm">
        <summary className="cursor-pointer text-text-secondary hover:text-text-primary">Show as table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-[11px] font-semibold text-text-muted">
                <th className="py-1.5 pr-4">Bucket ({clockLabel})</th>
                <th className="py-1.5 pr-4">Median</th>
                <th className="py-1.5 pr-4">
                  <Iqr />
                </th>
                <th className="py-1.5">n</th>
              </tr>
            </thead>
            <tbody className="font-mono tabular-nums">
              {tableRows.map((cell) => (
                <tr key={cell.key} className="border-t border-border-hairline hover:bg-bg-surface">
                  <td className="py-1.5 pr-4">{cell.key.startsWith("h") ? `${cell.label}:00` : cell.label}</td>
                  <td className="py-1.5 pr-4">{pct(cell.stats!.median)}</td>
                  <td className="py-1.5 pr-4">
                    {formatIqrRange(cell.stats!)}
                  </td>
                  <td className="py-1.5">
                    {cell.stats!.n}
                    {cell.stats!.insufficient_data ? ` · ${TOO_FEW_POSTS}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
