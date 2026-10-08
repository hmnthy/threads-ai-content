import Link from "next/link";
import { BrandLogo } from "@/components/BrandLogo";

const LINKS = [
  { href: "#problem", label: "Problem" },
  { href: "#approach", label: "Approach" },
  { href: "#proof", label: "Proof" },
  { href: "#method", label: "How it works" },
  { href: "#about", label: "About" },
];

// Navbar riêng cho landing (Tầng B) — pill trắng sticky, không tab; khác Nav.tsx (Tầng A).
// Mockup để pill tự xuống dòng nên ở ~1360px nút CTA rơi xuống hàng 2 và che nội dung: ở đây
// pill luôn 1 hàng, dưới lg chỉ còn logo + nút (ghi ở docs/design/ui-contract-audit.md).
export function LandingNav() {
  return (
    <div className="pointer-events-none sticky top-0 z-10 flex justify-center px-4 pt-4 sm:px-6">
      <nav
        aria-label="Landing"
        className="pointer-events-auto flex max-w-full flex-nowrap items-center gap-7 rounded-full border border-border-hairline bg-bg-card py-1.5 pl-[18px] pr-1.5"
      >
        <a href="#top" className="flex flex-none" aria-label="Unthreaded, back to top">
          {/* Lockup tĩnh 28px (ADR-0021); bản động chỉ dùng ở hero */}
          <BrandLogo variant="lockup" height={28} />
        </a>
        <div className="hidden gap-[22px] whitespace-nowrap text-sm lg:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-text-secondary hover:text-text-primary"
            >
              {link.label}
            </a>
          ))}
        </div>
        <Link
          href="/overview"
          className="flex h-10 flex-none items-center whitespace-nowrap rounded-full bg-amber-600 px-[18px] text-sm font-semibold text-white transition-colors hover:bg-amber-700"
        >
          View live dashboard
        </Link>
      </nav>
    </div>
  );
}
