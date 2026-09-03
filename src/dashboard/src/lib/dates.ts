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

export function formatDateLabel(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "2-digit", timeZone: "UTC" });
}
