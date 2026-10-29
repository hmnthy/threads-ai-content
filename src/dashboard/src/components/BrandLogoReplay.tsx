"use client";

import { useEffect, useState } from "react";

// Logo tháo nút phát lại theo chu kỳ (Thy 2026-10-29: "logo animation chạy mỗi 15s" — topbar app, navbar
// landing và hero landing). Dùng bản "chạy 1 lần" có sẵn (`unthreaded-lockup-animated-once.svg`, 6.553s,
// `animation-fill-mode: both` → dừng ở khung cuối = logo hoàn chỉnh); KHÔNG sửa file logo (ADR-0021,
// test_brand_assets_are_not_hand_edited giữ SHA-256 từng file).
//
// Phát lại: SVG trong <img> chạy CSS keyframes theo tài liệu của chính nó, gắn lại cùng URL không chắc
// chạy lại từ đầu (trình duyệt dùng chung bản đã giải mã). Vì vậy tải file 1 lần thành Blob, mỗi chu kỳ
// tạo 1 object URL mới → tài liệu SVG mới → hoạt cảnh chạy lại từ khung đầu, không tải mạng lần nữa.
// `prefers-reduced-motion: reduce` → chỉ bản tĩnh, không hẹn giờ; bật giữa phiên → về bản tĩnh ngay. Tab đang
// ẩn → không phát (không tạo URL vô ích).
const ONCE = "/brand/unthreaded-lockup-animated-once.svg";
const STATIC = "/brand/unthreaded-lockup.svg";
const ASPECT = 179.4 / 48; // viewBox của bản động

export function BrandLogoReplay({
  height,
  everyMs = 15_000,
  alt = "Unthreaded",
  className,
}: {
  height: number;
  everyMs?: number; // khoảng giữa 2 lần bắt đầu hoạt cảnh
  alt?: string;
  className?: string;
}) {
  const [src, setSrc] = useState(STATIC);
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    let cancelled = false;
    let blob: Blob | null = null;
    let current: string | null = null;
    const play = () => {
      if (!blob || cancelled || reduce.matches || document.hidden) return;
      const previous = current;
      current = URL.createObjectURL(blob);
      setSrc(current);
      // giải phóng URL cũ sau khi <img> đã đổi sang URL mới
      if (previous) window.setTimeout(() => URL.revokeObjectURL(previous), 1_000);
    };
    // giảm chuyển động lúc mở trang → không tải bản động (~400 KB) vô ích
    (reduce.matches ? Promise.resolve(null) : fetch(ONCE).then((response) => (response.ok ? response.blob() : null)))
      .then((b) => {
        blob = b;
        play();
      })
      .catch(() => {}); // lỗi mạng → giữ bản tĩnh
    const id = window.setInterval(play, everyMs);
    // người xem bật giảm chuyển động giữa phiên → về logo tĩnh ngay, các chu kỳ sau tự bỏ qua
    const onReduce = () => {
      if (reduce.matches) setSrc(STATIC);
    };
    reduce.addEventListener("change", onReduce);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      reduce.removeEventListener("change", onReduce);
      if (current) URL.revokeObjectURL(current);
    };
  }, [everyMs]);
  const width = Math.round(height * ASPECT);
  return (
    // eslint-disable-next-line @next/next/no-img-element -- SVG phục vụ nguyên bản (ADR-0021)
    <img src={src} alt={alt} width={width} height={height} className={className} style={{ height, width, flexShrink: 0 }} />
  );
}
