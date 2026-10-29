// Tên ngắn 6 khối của /topics — MỘT nguồn cho dải mục lục đầu trang và nhãn trên tiêu đề mỗi khối, để
// người đọc nhanh dò theo số + tên không gặp 2 tên cho 1 khối (ux-reviewer S4 2026-10-29)
export const TOPIC_SECTIONS = [
  ["intro", "01", "How to read this page"],
  ["topics", "02", "Topics and map"],
  ["engagement", "03", "Engagement by topic"],
  ["all-tests", "04", "All three rates"],
  ["stability", "05", "Stability"],
  ["terms", "06", "How it is computed"],
] as const;

export function sectionShort(id: (typeof TOPIC_SECTIONS)[number][0]): string {
  return TOPIC_SECTIONS.find(([key]) => key === id)![2];
}
