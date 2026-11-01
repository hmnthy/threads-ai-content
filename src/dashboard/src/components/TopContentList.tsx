"use client";

import { Answer, MethodSection, Section, topicOfUnit, UnitText } from "@/components/AppBlock";
import type { WindowAnalytics } from "@/lib/api";
import { OVERVIEW_SECTIONS, shortOf } from "@/lib/appSections";
import { formatPostDateParis } from "@/lib/dates";
import { count } from "@/lib/landing";

// Khối 02 của /overview: content unit đăng trong cửa sổ, xếp theo views của bài mở đầu (popularity_index, post-level) —
// KHÁC "Views" của dải hero (account-level, gồm cả reply). Chữ gốc luôn kèm tên topic tiếng Anh (B2). Dưới sm: thanh +
// số xuống dòng dưới chữ (ux-reviewer K9: chữ bị ép còn 1 từ/dòng ở 375px)
export function TopContentList({
  data,
  topicOf,
  topicCount,
}: {
  data: WindowAnalytics | null;
  topicOf: Record<string, string | null> | null;
  topicCount: number | null;
}) {
  const entries = data?.top_content_units ?? [];
  const maxViews = Math.max(...entries.map((entry) => entry.metrics.popularity_index), 1);
  const top = entries[0];

  return (
    <Section
      id="top"
      n="02"
      short={shortOf(OVERVIEW_SECTIONS, "top")}
      title="Which content units published in this window drew the most views?"
      purpose="Ranked by views of the opening post to date, not by the account's daily views in block 01."
    >
      <Answer>
        {!data
          ? "Loading the selected window…"
          : top
            ? `The most viewed content unit published in this window has ${count(top.metrics.popularity_index)} views on its opening post; the list shows the top ${entries.length} of ${count(data.content_unit_count)}.`
            : "No content unit was published in this window."}
      </Answer>
      {entries.length > 0 ? (
        <ol className="m-0 flex list-none flex-col p-0">
          {entries.map((entry, i) => {
            const width = Math.max((entry.metrics.popularity_index / maxViews) * 100, 2);
            return (
              <li
                key={entry.id}
                className="grid grid-cols-[28px_minmax(0,1fr)] gap-x-4 gap-y-2 border-t border-border-hairline py-4 first:border-t-0 sm:grid-cols-[28px_minmax(0,1fr)_200px_112px] sm:items-center"
              >
                <span className="font-mono text-[12.5px] font-semibold tabular-nums text-text-muted">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="flex min-w-0 flex-col gap-1">
                  <UnitText text={entry.text} topic={topicOfUnit(topicOf, entry.id)} topicCount={topicCount} />
                  <span className="font-mono text-[12.5px] tabular-nums text-text-muted">
                    {formatPostDateParis(entry.timestamp)}
                  </span>
                </span>
                <span aria-hidden="true" className="col-start-2 h-2 overflow-hidden rounded-full bg-bg-surface sm:col-start-auto">
                  <span className="block h-full rounded-full bg-amber-fill" style={{ width: `${width}%` }} />
                </span>
                <span className="col-start-2 text-[15px] font-semibold tabular-nums text-text-primary sm:col-start-auto sm:text-right">
                  {count(entry.metrics.popularity_index)} <span className="text-[13px] font-normal text-text-secondary">views</span>
                </span>
              </li>
            );
          })}
        </ol>
      ) : null}
      <MethodSection
        steps={[
          {
            title: "Ranking",
            plain: "Content units published in the window, sorted by their opening post's views as last read from Threads. Views of follow-up parts are not added. Each bar's length is its views divided by the largest in the list.",
            formula: "bar = views ÷ max(views in the list)",
          },
        ]}
        limits={[
          "Views are **counted to date**: a content unit published early in the window has had more time to collect them.",
          "A ranking describes the window; it does not say why a content unit drew more views.",
        ]}
      />
    </Section>
  );
}
