"use client";

import dynamic from "next/dynamic";
import { useMemo, useSyncExternalStore } from "react";
import type { Data, Layout } from "plotly.js";
import type { ContentUnit } from "@/lib/api";
import { CATEGORICAL_SLOTS, topicMark } from "@/lib/topicColors";

// plotly.js touches `window` at import time — must load client-side only, never
// during SSR/build (Next.js would otherwise fail `next build`).
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

// Mỗi topic 1 màu + hình (lib/topicColors.ts; Thy 2026-10-29 chọn đa sắc, thay 1 màu nhấn). Topic đang
// chọn: điểm to, đậm; topic khác: nhỏ, nhạt hơn — làm nổi bằng cỡ + độ đậm, không đổi màu nhận diện.
// Điểm nhiễu: vòng rỗng xám (UI-0004-noise-basis). Danh sách topic bên cạnh là chú giải có chữ.

interface Palette {
  cats: string[];
  point: string;
  text: string;
  grid: string;
  card: string;
}

// Plotly vẽ bằng WebGL, không đọc được `var(--token)` — đọc giá trị token thật từ CSS
function readPalette(): Palette {
  const css = getComputedStyle(document.documentElement);
  const token = (name: string) => css.getPropertyValue(name).trim();
  return {
    cats: Array.from({ length: CATEGORICAL_SLOTS }, (_, i) => token(`--cat-${i + 1}`)),
    point: token("--text-muted"),
    text: token("--text-secondary"),
    grid: token("--rule"),
    card: token("--bg-card"),
  };
}

const noopSubscribe = () => () => {};

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export function TopicMap3D({
  units,
  activeId,
  labelOf,
  topicIds,
}: {
  units: ContentUnit[]; // chỉ unit đã có toạ độ UMAP
  activeId: string | null; // topic id đang chọn; null = không làm nổi topic nào
  labelOf: Map<string, string>;
  topicIds: string[]; // thứ tự topic (quyết định màu, cùng thứ tự với danh sách)
}) {
  // Trang được server render (dữ liệu có sẵn ngay), nên lần render đầu ở client phải giống server:
  // `mounted` false lúc server render và lúc hydrate, true sau đó → mới đọc token và vẽ Plotly.
  const mounted = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const palette = useMemo<Palette | null>(() => (mounted ? readPalette() : null), [mounted]);

  const traces: Data[] = useMemo(() => {
    if (palette === null) return [];
    const hover = (unit: ContentUnit) =>
      `Topic: ${unit.topic ? (labelOf.get(unit.topic.topic_id) ?? unit.topic.topic_id) : "none (unclustered)"}<br>Original language: ${truncate(unit.text ?? unit.full_text, 110)}`;
    const trace = (subset: ContentUnit[], name: string, marker: Record<string, unknown>): Data => ({
      type: "scatter3d",
      mode: "markers",
      name,
      x: subset.map((unit) => unit.umap![0]),
      y: subset.map((unit) => unit.umap![1]),
      z: subset.map((unit) => unit.umap![2]),
      text: subset.map(hover),
      hovertemplate: "%{text}<extra></extra>",
      marker,
    });
    const noise = units.filter((unit) => unit.topic === null);
    const out: Data[] = [
      trace(noise, "Unclustered", { size: 3, color: palette.point, opacity: 0.45, symbol: "circle-open" }),
    ];
    // Topic đang chọn vẽ sau cùng để nằm trên
    const ordered = [...topicIds.filter((id) => id !== activeId), ...topicIds.filter((id) => id === activeId)];
    for (const id of ordered) {
      const mark = topicMark(topicIds.indexOf(id));
      const on = id === activeId;
      out.push(
        trace(
          units.filter((unit) => unit.topic?.topic_id === id),
          labelOf.get(id) ?? id,
          {
            size: on ? 7 : 4.5,
            color: palette.cats[mark.slot - 1],
            opacity: activeId === null || on ? 0.95 : 0.55,
            symbol: mark.shape,
          },
        ),
      );
    }
    return out;
  }, [units, palette, activeId, labelOf, topicIds]);

  // Biên mỗi trục = min/max ± 5%: không chấm nào (kể cả topic đang chọn) bị cắt ở mép khung.
  // Trục không đơn vị nên khung lập phương, không kéo dãn theo dữ liệu.
  const ranges = useMemo(() => {
    return [0, 1, 2].map((axis): [number, number] => {
      const values = units.map((unit) => unit.umap![axis]);
      const lo = Math.min(...values);
      const hi = Math.max(...values);
      const pad = (hi - lo) * 0.05 || 1;
      return [lo - pad, hi + pad];
    });
  }, [units]);
  // Memo + `uirevision` cố định: đổi topic chỉ đổi traces, Plotly giữ nguyên góc xoay
  // người xem đã chỉnh (thiếu uirevision thì mỗi lần chọn topic camera bị reset).
  const layout: Partial<Layout> | null = useMemo(
    () =>
      palette === null
        ? null
        : {
            paper_bgcolor: palette.card,
            font: { color: palette.text, family: "var(--font-inter), system-ui, sans-serif", size: 12 },
            margin: { l: 0, r: 0, t: 0, b: 0 },
            showlegend: false,
            uirevision: "topic-map",
            scene: {
              bgcolor: palette.card,
              aspectmode: "cube",
              camera: { eye: { x: 1.25, y: 1.25, z: 0.9 } },
              xaxis: { title: { text: "" }, range: ranges[0], showticklabels: false, gridcolor: palette.grid, zerolinecolor: palette.grid },
              yaxis: { title: { text: "" }, range: ranges[1], showticklabels: false, gridcolor: palette.grid, zerolinecolor: palette.grid },
              zaxis: { title: { text: "" }, range: ranges[2], showticklabels: false, gridcolor: palette.grid, zerolinecolor: palette.grid },
            },
          },
    [palette, ranges],
  );

  return (
    <div className="h-[460px] rounded-xl border border-border-hairline" aria-hidden="true">
      {layout !== null ? (
        <Plot
          data={traces}
          layout={layout}
          config={{ displaylogo: false, displayModeBar: false, responsive: true }}
          style={{ width: "100%", height: "100%" }}
        />
      ) : (
        <div className="h-full animate-pulse rounded-xl bg-bg-surface" />
      )}
    </div>
  );
}
