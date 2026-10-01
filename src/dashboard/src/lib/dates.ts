// Ngày dạng "YYYY-MM-DD", luôn xử lý ở UTC (Date.parse hiểu chuỗi ngày-thuần như
// UTC midnight) — tránh lệch 1 ngày do timezone trình duyệt, không cần thư viện
// ngoài (date-fns/dayjs) cho vài phép toán đơn giản này.

const DAY_MS = 86_400_000;

export function daysBetweenInclusive(start: string, end: string): number {
  const a = Date.parse(`${start}T00:00:00Z`);
  const b = Date.parse(`${end}T00:00:00Z`);
  return Math.round((b - a) / DAY_MS) + 1;
}

export function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

// Nhãn trục của chart nhiều năm: "Sep 2024" — "Sep 02" thiếu năm từng làm trục
// 2 năm đọc như nhảy tháng (Sep → Mar → Sep)
export function formatMonthYear(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

export function formatFullDate(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric", timeZone: "UTC" });
}

// Timestamp của post (ISO, UTC) hiển thị theo giờ Paris — nơi tác giả sống. Mọi trang
// dùng chung 2 hàm này; cắt chuỗi `slice(0, 10)` cho ra ngày UTC, lệch 1 ngày với bài
// đăng sau 22:00/23:00 giờ Paris.
const PARIS_DATE = new Intl.DateTimeFormat("en-US", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "short",
  day: "2-digit",
});
const PARIS_DATE_TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatPostDateParis(iso: string): string {
  return PARIS_DATE.format(new Date(iso));
}

export function formatPostDateTimeParis(iso: string): string {
  return PARIS_DATE_TIME.format(new Date(iso));
}
