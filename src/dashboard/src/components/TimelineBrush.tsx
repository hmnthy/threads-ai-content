"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { DailyViewsPoint } from "@/lib/api";
import { addDays, formatDateLabel } from "@/lib/dates";

// Thành phần chữ ký của sản phẩm (docs/claude/design-system.md §5) — port từ
// src/dashboard/mockups/overview-amber.dc.html (pointer-capture drag 2 tay cầm +
// pan giữa + keyboard nudge + preset), nhưng khác mockup ở 2 điểm CỐT LÕI vì đây
// là data thật, không phải demo tĩnh:
// 1. `days`/`minDate`/`maxDate` tính từ `points` thật (không hardcode 90 ngày).
// 2. Số liệu KPI/hero KHÔNG tự tính client-side từ series — chỉ rail/chart tự vẽ
//    lại real-time khi kéo; số liệu thật (`onWindowCommit`) debounce 300ms, bắn
//    lúc thả tay/nhả phím/bấm preset — tránh spam network mỗi pixel kéo (mockup
//    dùng data giả tĩnh nên không có chi phí này).

const COMMIT_DEBOUNCE_MS = 300;
const MIN_WINDOW_DAYS = 5;
type DragMode = "start" | "end" | "pan" | null;

interface TimelineBrushProps {
  points: DailyViewsPoint[];
  onWindowCommit: (start: string, end: string) => void;
}

function findPeakWeek(points: DailyViewsPoint[]): { startIndex: number; endIndex: number } {
  const n = points.length;
  if (n === 0) return { startIndex: 0, endIndex: 0 };
  const windowSize = Math.min(7, n);
  let bestSum = -Infinity;
  let bestStart = 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    sum += points[i].views;
    if (i >= windowSize) sum -= points[i - windowSize].views;
    if (i >= windowSize - 1 && sum > bestSum) {
      bestSum = sum;
      bestStart = i - windowSize + 1;
    }
  }
  return { startIndex: bestStart, endIndex: bestStart + windowSize - 1 };
}

export function TimelineBrush({ points, onWindowCommit }: TimelineBrushProps) {
  const days = points.length;
  const minDate = points[0]?.date;

  const defaultWindow = useMemo((): [number, number] => {
    if (days <= 1) return [0, 1];
    const n = Math.min(30, days);
    return [(days - n) / days, 1];
  }, [days]);

  const [w0, setW0] = useState(defaultWindow[0]);
  const [w1, setW1] = useState(defaultWindow[1]);
  const [drag, setDrag] = useState<DragMode>(null);
  const railRef = useRef<HTMLDivElement>(null);
  const panFromRef = useRef<number | null>(null);
  const commitTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialCommitDone = useRef(false);

  useEffect(() => () => {
    if (commitTimeoutRef.current) clearTimeout(commitTimeoutRef.current);
  }, []);

  const commitWindow = useMemo(
    () =>
      (nextW0: number, nextW1: number, opts: { debounce?: boolean } = {}) => {
        setW0(nextW0);
        setW1(nextW1);
        if (!minDate || days <= 1) return;
        const fire = () => {
          const i0 = Math.round(nextW0 * (days - 1));
          const i1 = Math.round(nextW1 * (days - 1));
          onWindowCommit(addDays(minDate, i0), addDays(minDate, i1));
        };
        if (commitTimeoutRef.current) clearTimeout(commitTimeoutRef.current);
        if (opts.debounce === false) {
          fire();
        } else {
          commitTimeoutRef.current = setTimeout(fire, COMMIT_DEBOUNCE_MS);
        }
      },
    [minDate, days, onWindowCommit],
  );

  // Commit 1 lần khi series vừa sẵn sàng, để hero/KPI có số liệu ngay từ đầu
  // (count-up lần load đầu — §8 Motion) thay vì chờ user tự kéo trước.
  useEffect(() => {
    if (days > 0 && !initialCommitDone.current) {
      initialCommitDone.current = true;
      commitWindow(defaultWindow[0], defaultWindow[1], { debounce: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  if (days === 0) {
    return (
      <section className="flex flex-col items-center gap-2 rounded-xl border border-border-hairline bg-bg-card p-12 text-center">
        <p className="text-sm text-text-secondary">No daily views ingested yet.</p>
        <p className="font-mono text-xs text-text-muted">
          Run <code>python -m src.pipeline.daily_views</code>
        </p>
      </section>
    );
  }

  const pctFromEvent = (e: { clientX: number }): number | null => {
    const el = railRef.current;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
  };

  const minSpan = MIN_WINDOW_DAYS / days;

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const p = pctFromEvent(e);
    if (p === null) return;
    if (drag === "start") {
      commitWindow(Math.min(p, w1 - minSpan), w1);
    } else if (drag === "end") {
      commitWindow(w0, Math.max(p, w0 + minSpan));
    } else if (drag === "pan" && panFromRef.current !== null) {
      const d = p - panFromRef.current;
      const width = w1 - w0;
      const nextW0 = Math.min(Math.max(w0 + d, 0), 1 - width);
      commitWindow(nextW0, nextW0 + width);
      panFromRef.current = p;
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    setDrag(null);
    panFromRef.current = null;
  };

  const onStartDown = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag("start");
  };
  const onEndDown = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag("end");
  };
  const onPanDown = (e: React.PointerEvent) => {
    const p = pctFromEvent(e);
    if (p === null) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    panFromRef.current = p;
    setDrag("pan");
  };

  function nudge(which: "start" | "end", dir: 1 | -1) {
    const step = 1 / days;
    if (which === "start") {
      commitWindow(Math.min(Math.max(w0 + dir * step, 0), w1 - minSpan), w1);
    } else {
      commitWindow(w0, Math.max(Math.min(w1 + dir * step, 1), w0 + minSpan));
    }
  }
  const onStartKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      nudge("start", -1);
    }
    if (e.key === "ArrowRight") {
      e.preventDefault();
      nudge("start", 1);
    }
  };
  const onEndKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      nudge("end", -1);
    }
    if (e.key === "ArrowRight") {
      e.preventDefault();
      nudge("end", 1);
    }
  };

  function setPreset(kind: "30d" | "60d" | "90d" | "peak") {
    if (kind === "peak") {
      const peak = findPeakWeek(points);
      commitWindow(peak.startIndex / (days - 1 || 1), peak.endIndex / (days - 1 || 1), {
        debounce: false,
      });
      return;
    }
    const n = Math.min({ "30d": 30, "60d": 60, "90d": 90 }[kind], days);
    commitWindow(Math.max((days - n) / days, 0), 1, { debounce: false });
  }

  function isPresetActive(kind: "30d" | "60d" | "90d" | "peak"): boolean {
    if (kind === "peak") {
      const peak = findPeakWeek(points);
      return (
        Math.abs(w0 - peak.startIndex / (days - 1 || 1)) < 0.01 &&
        Math.abs(w1 - peak.endIndex / (days - 1 || 1)) < 0.01
      );
    }
    const n = Math.min({ "30d": 30, "60d": 60, "90d": 90 }[kind], days);
    return Math.abs(w1 - 1) < 0.005 && Math.abs(w0 - (days - n) / days) < 0.008;
  }

  const i0 = Math.round(w0 * (days - 1));
  const i1 = Math.round(w1 * (days - 1));
  const startDate = addDays(minDate!, i0);
  const endDate = addDays(minDate!, i1);
  const spanDays = i1 - i0 + 1;

  const maxViews = Math.max(...points.map((p) => p.views), 1);
  const chartPoints = points.map(
    (p, i) =>
      [+((i / Math.max(days - 1, 1)) * 1200).toFixed(1), +(216 - (p.views / maxViews) * 190).toFixed(1)] as const,
  );
  const linePath = chartPoints.map(([x, y]) => `${x},${y}`).join(" ");
  const areaPath = `0,216 ${linePath} 1200,216`;
  const x0 = +(w0 * 1200).toFixed(1);
  const x1 = +(w1 * 1200).toFixed(1);

  const ticks = Array.from({ length: 13 }, (_, i) => {
    const p = i / 12;
    const major = i % 3 === 0;
    const inWindow = p >= w0 && p <= w1;
    return { p, major, inWindow };
  });

  const axisLabels = [0, 0.25, 0.5, 0.75, 1].map((f) =>
    formatDateLabel(addDays(minDate!, Math.round(f * (days - 1)))),
  );

  const presets: { key: "30d" | "60d" | "90d" | "peak"; label: string }[] = [
    { key: "30d", label: "30d" },
    { key: "60d", label: "60d" },
    { key: "90d", label: "90d" },
    { key: "peak", label: "Peak week" },
  ];

  return (
    <section className="flex flex-col gap-3.5 rounded-xl border border-border-hairline bg-bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold text-text-primary">
            Daily views · drag the window to rescale every metric
          </span>
          <span className="font-mono text-xs tabular-nums text-text-muted">
            {formatDateLabel(startDate)} → {formatDateLabel(endDate)} · {spanDays} days
          </span>
        </div>
        <div className="flex items-center gap-2">
          {presets.map((preset) => {
            const active = isPresetActive(preset.key);
            return (
              <button
                key={preset.key}
                type="button"
                onClick={() => setPreset(preset.key)}
                className={`h-8 flex-none rounded-full border px-3.5 font-mono text-[12.5px] font-medium ${
                  active
                    ? "border-amber-600 bg-amber-soft text-amber-600"
                    : "border-border-hairline bg-bg-surface text-text-secondary"
                }`}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      </div>

      <svg
        viewBox="0 0 1200 240"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Daily views over ${days} days`}
        className="block h-[220px] w-full"
      >
        <line x1="0" y1="48" x2="1200" y2="48" stroke="var(--rule)" strokeWidth="1" />
        <line x1="0" y1="112" x2="1200" y2="112" stroke="var(--rule)" strokeWidth="1" />
        <line x1="0" y1="176" x2="1200" y2="176" stroke="var(--rule)" strokeWidth="1" />
        <polygon points={areaPath} fill="var(--amber-600)" fillOpacity="0.1" />
        <polyline points={linePath} fill="none" stroke="var(--amber-600)" strokeWidth="2" />
        <rect x="0" y="0" width={x0} height="240" fill="var(--bg-page)" fillOpacity="0.72" />
        <rect x={x1} y="0" width={1200 - x1} height="240" fill="var(--bg-page)" fillOpacity="0.72" />
        <line x1={x0} y1="0" x2={x0} y2="240" stroke="var(--amber-600)" strokeWidth="1" strokeOpacity="0.5" />
        <line x1={x1} y1="0" x2={x1} y2="240" stroke="var(--amber-600)" strokeWidth="1" strokeOpacity="0.5" />
      </svg>

      <div ref={railRef} className="relative h-11 touch-none">
        <div className="absolute top-[21px] right-0 left-0 h-0.5 rounded-full bg-[var(--rule)]" />
        {ticks.map((tick, i) => (
          <span
            key={i}
            className="absolute w-px"
            style={{
              top: tick.major ? 15 : 17,
              left: `${(tick.p * 100).toFixed(3)}%`,
              height: tick.major ? 14 : 10,
              background: tick.inWindow ? "rgba(180,83,9,0.35)" : "var(--rule)",
            }}
          />
        ))}
        <div
          onPointerDown={onPanDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          className="absolute top-0 flex h-11 cursor-grab touch-none items-center"
          style={{ left: `${(w0 * 100).toFixed(3)}%`, width: `${((w1 - w0) * 100).toFixed(3)}%` }}
        >
          <span className="block h-0.5 w-full rounded-full bg-amber-600" />
        </div>
        <div
          role="slider"
          tabIndex={0}
          aria-label="Window start"
          aria-valuemin={0}
          aria-valuemax={days - 1}
          aria-valuenow={i0}
          aria-valuetext={formatDateLabel(startDate)}
          onPointerDown={onStartDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onKeyDown={onStartKey}
          className="absolute top-0 flex h-11 w-11 cursor-ew-resize touch-none items-center justify-center"
          style={{ left: `calc(${(w0 * 100).toFixed(3)}% - 22px)` }}
        >
          <span className="h-[13px] w-[13px] rounded-full border-2 border-amber-600 bg-white shadow-[0_1px_4px_rgba(17,24,39,0.20)]" />
        </div>
        <div
          role="slider"
          tabIndex={0}
          aria-label="Window end"
          aria-valuemin={0}
          aria-valuemax={days - 1}
          aria-valuenow={i1}
          aria-valuetext={formatDateLabel(endDate)}
          onPointerDown={onEndDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onKeyDown={onEndKey}
          className="absolute top-0 flex h-11 w-11 cursor-ew-resize touch-none items-center justify-center"
          style={{ left: `calc(${(w1 * 100).toFixed(3)}% - 22px)` }}
        >
          <span className="h-[13px] w-[13px] rounded-full border-2 border-amber-600 bg-white shadow-[0_1px_4px_rgba(17,24,39,0.20)]" />
        </div>
      </div>

      <div className="flex justify-between font-mono text-[11px] text-text-muted">
        {axisLabels.map((label, i) => (
          <span key={i}>{label}</span>
        ))}
      </div>
    </section>
  );
}
