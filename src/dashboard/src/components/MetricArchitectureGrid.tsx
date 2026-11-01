"use client";

import { Answer, MethodSection, Section, TYPE } from "@/components/AppBlock";
import { OVERVIEW_SECTIONS, shortOf } from "@/lib/appSections";
import { andList } from "@/lib/landing";

interface IndexCard {
  name: string;
  formula: string;
  status: "live" | "deferred";
  note: string;
}

// 6 index của docs/claude/data-model.md "Metric Architecture" (popularity_index, engagement_rate, share_rate,
// conversation_rate + 2 chưa làm), tách riêng, không blend thành 1 điểm số. Tên hiển thị cùng chữ với tab và Key
// numbers các trang (copy-reviewer 2026-10-31). Nội dung tĩnh, không phụ thuộc cửa sổ thời gian đang chọn.
const INDICES: IndexCard[] = [
  { name: "Views", formula: "views", status: "live", note: "How many times the opening post was seen. Every rate below divides by it." },
  {
    name: "Engagement rate",
    formula: "(likes + replies + reposts + quotes) ÷ views × 100",
    status: "live",
    note: "Interactions per 100 views of the opening post. One viewer can interact more than once, so it is not the share of viewers who interacted. The denominator is views, not followers.",
  },
  {
    name: "Share rate",
    formula: "(reposts + quotes) ÷ views × 100",
    status: "live",
    note: "Reposts and quotes only: Threads reports no separate share count for a post.",
  },
  {
    name: "Conversation rate",
    formula: "replies ÷ views × 100",
    status: "live",
    note: "All replies to the opening post: the only reply count Threads reports per post.",
  },
  {
    name: "View velocity",
    formula: "Δviews ÷ Δt  (Δt in hours between two reads)",
    status: "deferred",
    note: "Views are re-read every 4 hours since Aug 31, 2026, but only while the collecting laptop is awake, so the series has long overnight gaps. Not built yet.",
  },
  {
    name: "Longevity",
    formula: "(interactions at 72 h − interactions at 24 h) ÷ interactions at 72 h",
    status: "deferred",
    note: "Formula specified, not built yet. It needs interactions read 24 h and 72 h after posting."
  },
];

// Câu trả lời viết số bằng chữ ở đầu câu (copy-reviewer 2026-10-31)
const NUMBER_WORDS: Record<number, string> = { 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six" };

// Khối 03 của /overview (khuôn khối chung): 6 chỉ số tách riêng; thẻ chưa làm có nền sunken + chip (UI-0001-status-labels)
export function MetricArchitectureGrid() {
  const live = INDICES.filter((index) => index.status === "live").length;
  const deferred = INDICES.filter((index) => index.status === "deferred").map((index) => index.name.toLowerCase());
  const deferredText = andList(deferred);
  return (
    <Section
      id="measures"
      n="03"
      short={shortOf(OVERVIEW_SECTIONS, "measures")}
      title="Which measures does the dashboard use?"
      purpose="Six measures, kept separate: nothing is blended into a single score."
    >
      <Answer>
        {NUMBER_WORDS[live] ?? live} are live: views and three rates per 100 views.{" "}
        {deferredText.charAt(0).toUpperCase() + deferredText.slice(1)} are specified but not built yet.
      </Answer>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {INDICES.map((index) => (
          <div
            key={index.name}
            className={`flex flex-col gap-2.5 rounded-xl border border-border-hairline p-5 ${
              index.status === "live" ? "bg-bg-card" : "bg-bg-sunken"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              {/* Tên thẻ là heading thật (T6: không tiêu đề giả) — h3 vai box-title, ngay dưới tiêu đề khối h2 */}
              <h3
                data-ux-role="box-title"
                className={`m-0 ${TYPE.h4}`}
              >
                {index.name}
              </h3>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[12px] font-medium ${
                  index.status === "live" ? "bg-amber-soft text-amber-600" : "bg-bg-surface text-text-secondary"
                }`}
              >
                {index.status}
              </span>
            </div>
            <span className="font-mono text-[12.5px] leading-relaxed break-words text-text-secondary">
              {index.formula}
            </span>
            <span className={TYPE.note}>{index.note}</span>
          </div>
        ))}
      </div>
      <MethodSection
        steps={[
          {
            title: "One denominator",
            plain: "Every rate divides by the views of the content unit's opening post, the number the Threads API reports for that post, not by followers.",
            formula: "rate = count ÷ views × 100",
          },
          {
            title: "Kept separate",
            plain: "Each measure answers its own question (how often the opening post was seen, how often it drew any interaction, a repost or quote, or a reply), so none is weighted into a combined score.",
          },
        ]}
        limits={[
          "Threads exposes **no separate shares field**, so the share rate counts reposts and quotes only.",
          "The conversation rate uses the one total reply count Threads reports per post, so it cannot separate followers' replies from the author's.",
          "Longevity needs readings exactly 24 h and 72 h after posting, and view velocity needs readings close together; overnight gaps allow neither yet.",
        ]}
      />
    </Section>
  );
}
