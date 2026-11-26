import type { ReactNode } from "react";
import { Formula, rich, TYPE } from "@/components/AppBlock";

// Bảng thuật ngữ của một trang app: các nhóm mục, mỗi mục có mỏ neo `term-<id>` để link `#term-<id>` (TermLink,
// TermMore, nhãn Key numbers) nhảy tới. Tách từ `TopicMethods.tsx` (PR 2a RAG, Thy chốt 2026-11-25) để /topics và
// /rag-pipeline dùng một markup — trang gọi: /topics (`TopicMethods`), /rag-pipeline (`RagPipelineView`).
// Mỗi mục: chữ thường → công thức → nghĩa từng ký hiệu → giá trị của lần chạy này.

export interface TermEntry {
  id: string; // anchor `term-<id>` — các khối trên trang link tới đây
  term: string;
  plain: ReactNode;
  formula?: string[];
  where?: ReactNode[];
  thisRun?: ReactNode;
}

export interface TermGroup {
  title: string;
  lead: string;
  entries: TermEntry[];
}

export function TermGroups({ intro, groups }: { intro: ReactNode; groups: TermGroup[] }) {
  return (
    <>
      <div className="flex flex-col gap-2">
        <p className={`m-0 ${TYPE.measure} ${TYPE.body}`}>{intro}</p>
      </div>
      {groups.map((group) => (
        <div key={group.title} className="flex flex-col gap-2 border-t border-border-hairline pt-7">
          <div className="flex flex-col gap-1">
            <h3 className={`m-0 ${TYPE.h3}`}>{group.title}</h3>
            <p className={`m-0 ${TYPE.note}`}>{group.lead}</p>
          </div>
          <dl className="m-0 flex flex-col">
            {group.entries.map((entry) => (
              <div
                key={entry.id}
                id={`term-${entry.id}`}
                className="grid scroll-mt-24 grid-cols-1 gap-x-8 gap-y-2 border-b border-bg-surface py-4 last:border-b-0 md:grid-cols-[220px_minmax(0,1fr)]"
              >
                <dt className={TYPE.h4}>{entry.term}</dt>
                <dd className="m-0 flex flex-col gap-2.5">
                  <p className={`m-0 ${TYPE.measure} ${TYPE.body} [text-wrap:pretty]`}>{entry.plain}</p>
                  {entry.formula ? (
                    // xuống dòng được ở khổ hẹp — không thanh cuộn lồng (luật bố cục)
                    <div className="flex w-full flex-col gap-0.5 rounded-lg border border-border-hairline bg-bg-sunken px-3.5 py-2.5">
                      {entry.formula.map((line) => (
                        <Formula key={line}>{line}</Formula>
                      ))}
                    </div>
                  ) : null}
                  {entry.where && entry.where.length > 0 ? (
                    <ul className={`m-0 flex ${TYPE.measure} list-disc flex-col gap-1 pl-5 text-[13px] leading-[1.55] text-text-secondary marker:text-text-muted`}>
                      {entry.where.map((item, i) => (
                        <li key={i}>{rich(item)}</li>
                      ))}
                    </ul>
                  ) : null}
                  {entry.thisRun ? (
                    <p className={`m-0 ${TYPE.measure} text-[13px] leading-[1.55] text-text-secondary`}>
                      <span className="font-semibold text-text-primary">This run: </span>
                      {entry.thisRun}
                    </p>
                  ) : null}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </>
  );
}
