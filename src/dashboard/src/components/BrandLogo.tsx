// Logo Unknot (ADR-0021). File gốc duy nhất ở `public/brand/` — không sửa tay hình học hay màu
// (docs/design/brand-assets.md). Vị trí dùng chốt trong ADR-0021: navbar landing và topbar dashboard
// dùng `lockup` tĩnh; `lockup-animated` (lặp) chỉ ở hero landing; `mark` ở khối CTA.
//
// Dùng <img> thay next/image: next/image không tối ưu được SVG, và SVG động chạy bằng CSS keyframes
// bên trong file nên cần phục vụ nguyên bản; <picture> đổi sang bản tĩnh khi người xem bật
// `prefers-reduced-motion`.

type BrandLogoVariant = "lockup" | "lockup-animated" | "mark";

const ASSETS: Record<BrandLogoVariant, { src: string; aspect: number }> = {
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
