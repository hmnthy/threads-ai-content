// Tên ngắn các khối của /overview và /analytics — MỘT nguồn cho dải mục lục đầu trang (`PageHeader`) và nhãn trên
// tiêu đề mỗi khối (`Section`), như `topicSections.ts` của /topics
// Thứ tự Thy chốt 2026-10-31: 2 khối trả lời câu hỏi đầu trang đọc liền, khối định nghĩa chỉ số về cuối
export const OVERVIEW_SECTIONS = [
  ["window", "01", "Time window"],
  ["top", "02", "Most viewed"],
  ["measures", "03", "Measures"],
] as const;

export const ANALYTICS_SECTIONS = [
  ["ranking", "01", "Top by rate"],
  ["posting-time", "02", "Posting time"],
] as const;

// Định nghĩa đơn vị đếm dưới câu hỏi đầu trang Overview + Analytics (Thy 2026-10-31: một tên "content units" cho mọi
// trang; copy-reviewer: trang nào dùng thì trang đó định nghĩa). Cùng câu với khối 01 của /topics
export const CONTENT_UNIT =
  "A **content unit** is one post as published, plus the follow-up parts its author added in the same thread; comments are left out.";

// Định nghĩa "rate" trước khi trang dùng (copy-reviewer lượt 3: khối định nghĩa chỉ số nằm cuối Overview)
export const RATE_DEFINITION =
  "Each **rate** counts interactions per 100 views of a content unit's opening post (its first post).";

type Sections = readonly (readonly [string, string, string])[];

export function shortOf(sections: Sections, id: string): string {
  return sections.find(([key]) => key === id)?.[2] ?? id;
}
