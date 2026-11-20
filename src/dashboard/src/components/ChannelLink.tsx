// Link tới kênh Threads thật của dữ liệu — MỘT nguồn cho landing (hero, Problem, About) và pill tài khoản ở topbar app
// (Thy 2026-11-19: "bấm vào tên thydilammuon dẫn đến kênh Threads thật"). URL kiểm live 2026-11-19: threads.com trả 200,
// threads.net chuyển hướng 301 sang threads.com. Mở tab mới vì người đọc đang ở giữa trang.
import type { ReactNode } from "react";

export const CHANNEL_HANDLE = "thydilammuon";
export const CHANNEL_URL = `https://www.threads.com/@${CHANNEL_HANDLE}`;

export function ChannelLink({ className, children }: { className?: string; children?: ReactNode }) {
  return (
    <a
      href={CHANNEL_URL}
      target="_blank"
      rel="noopener noreferrer"
      className={className ?? "font-medium text-amber-700 underline underline-offset-4"}
    >
      {children ?? `@${CHANNEL_HANDLE}`}
    </a>
  );
}
