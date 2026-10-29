// Logo Unknot (ADR-0021). File gốc duy nhất ở `public/brand/` — không sửa tay hình học hay màu
// (docs/design/brand-assets.md). Vị trí theo ADR-0021, cập nhật Thy 2026-10-29: topbar app, navbar
// landing và hero landing dùng `lockup-replay` (bản "chạy 1 lần" phát lại mỗi 15 giây, BrandLogoReplay);
// `mark` ở khối CTA; `lockup` tĩnh ở footer. `lockup-animated` (lặp liên tục) không còn chỗ dùng.
//
// Dùng <img> thay next/image: next/image không tối ưu được SVG, và SVG động chạy bằng CSS keyframes
// bên trong file nên cần phục vụ nguyên bản; <picture> đổi sang bản tĩnh khi người xem bật
// `prefers-reduced-motion`.

import { BrandLogoReplay } from "@/components/BrandLogoReplay";

type BrandLogoVariant = "lockup" | "lockup-animated" | "lockup-replay" | "mark";

const ASSETS: Record<Exclude<BrandLogoVariant, "lockup-replay">, { src: string; aspect: number }> = {
  // aspect = rộng / cao theo viewBox của file SVG
  lockup: { src: "/brand/unthreaded-lockup.svg", aspect: 179.43 / 48 },
  "lockup-animated": { src: "/brand/unthreaded-lockup-animated.svg", aspect: 179.4 / 48 },
  mark: { src: "/brand/unthreaded-mark.svg", aspect: 1 },
};

const STATIC_FALLBACK = "/brand/unthreaded-lockup.svg";

interface BrandLogoProps {
  variant?: BrandLogoVariant;
  height: number;
  // "" khi logo chỉ để trang trí bên cạnh chữ "Unthreaded" (VD khối CTA của landing)
  alt?: string;
  // Gắn vào phần tử ngoài cùng (`<picture>` với bản động) để layout giống nhau ở mọi biến thể
  className?: string;
}

export function BrandLogo({
  variant = "lockup",
  height,
  alt = "Unthreaded",
  className,
}: BrandLogoProps) {
  if (variant === "lockup-replay") return <BrandLogoReplay height={height} alt={alt} className={className} />;
  const { src, aspect } = ASSETS[variant];
  const width = Math.round(height * aspect);
  // Rộng cố định (không `auto`): trong flex cột, ảnh `width: auto` bị kéo giãn theo phần tử anh em
  const style = { height, width, flexShrink: 0 };
  if (variant !== "lockup-animated") {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- SVG phục vụ nguyên bản (ADR-0021)
      <img src={src} alt={alt} width={width} height={height} className={className} style={style} />
    );
  }
  return (
    <picture className={className} style={{ display: "block", ...style }}>
      <source media="(prefers-reduced-motion: reduce)" srcSet={STATIC_FALLBACK} />
      <img src={src} alt={alt} width={width} height={height} style={style} />
    </picture>
  );
}
