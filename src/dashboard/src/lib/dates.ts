// Ngày dạng "YYYY-MM-DD", luôn xử lý ở UTC (Date.parse hiểu chuỗi ngày-thuần như
// UTC midnight) — tránh lệch 1 ngày do timezone trình duyệt, không cần thư viện
// ngoài (date-fns/dayjs) cho vài phép toán đơn giản này.

const DAY_MS = 86_400_000;

export function daysBetweenInclusive(start: string, end: string): number {
  const a = Date.parse(`${start}T00:00:00Z`);
  const b = Date.parse(`${end}T00:00:00Z`);
  return Math.round((b - a) / DAY_MS) + 1;
}

// Nhãn trục của chart nhiều năm: "Sep 2024" — "Sep 02" thiếu năm từng làm trục
// 2 năm đọc như nhảy tháng (Sep → Mar → Sep)
export function formatMonthYear(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

export function formatFullDate(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

// Một kiểu ngày trong thân mọi trang: "Oct 2, 2026" (+ ", 12:52 PM" khi cần giờ) — Thy chốt 2026-11-01;
// ISO chỉ ở chip "data as of" đầu trang (`parisTime`).
// Timestamp của post (ISO, UTC) hiển thị theo giờ Paris — nơi tác giả sống. Mọi trang
// dùng chung 2 hàm này; cắt chuỗi `slice(0, 10)` cho ra ngày UTC, lệch 1 ngày với bài
// đăng sau 22:00/23:00 giờ Paris.
const PARIS_DATE = new Intl.DateTimeFormat("en-US", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "short",
  day: "numeric",
});
const PARIS_DATE_TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

export function formatPostDateParis(iso: string): string {
  return PARIS_DATE.format(new Date(iso));
}

// Ngày đăng "YYYY-MM-DD" theo giờ Paris — cùng quy ước với bộ lọc bài của /analytics/window
// (`author_day`, src/models/days.py, ADR-0034); không cắt `slice(0, 10)` (ngày UTC)
const PARIS_DAY_PARTS = new Intl.DateTimeFormat("en-US", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

// Ngày Pacific — ranh giới ngày của chuỗi views theo ngày (Meta, ADR-0034); chỉ dùng để đếm bài có ngày Paris khác
// ngày Pacific (đăng trước 9h sáng Paris), không dùng để lọc bài
const PACIFIC_DAY_PARTS = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Los_Angeles",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

// "" khi timestamp không đọc được — người gọi bỏ qua bài đó, không làm hỏng cả trang (code-reviewer)
function dayIn(format: Intl.DateTimeFormat, iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const parts = format.formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function parisDay(iso: string): string {
  return dayIn(PARIS_DAY_PARTS, iso);
}

export function pacificDay(iso: string): string {
  return dayIn(PACIFIC_DAY_PARTS, iso);
}

export function formatPostDateTimeParis(iso: string): string {
  return PARIS_DATE_TIME.format(new Date(iso));
}
