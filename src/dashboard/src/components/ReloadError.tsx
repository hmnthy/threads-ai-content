"use client";

import { useRouter } from "next/navigation";
import { LoadError } from "@/components/AppBlock";

// LoadError cho trang server component (không truyền được hàm onRetry từ server): thử lại = tải lại dữ liệu server
// của trang (cùng cách AnalyticsBreakdown `UnitBlock`; ux-reviewer 2026-11-04: /topics tự viết lỗi bằng link)
export function ReloadError({ what }: { what?: string }) {
  const router = useRouter();
  return <LoadError what={what} onRetry={() => router.refresh()} />;
}
