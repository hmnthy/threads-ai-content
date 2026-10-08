import Link from "next/link";
import { BrandLogo } from "@/components/BrandLogo";

// Khối CTA cuối trên dải tối (handoff §3.7, design-system §2.6). Mark 52px là trang trí cạnh
// tiêu đề nên alt="" (ADR-0021). Chưa có trang methodology riêng → nút trỏ sơ đồ "How it works";
// nút repo bỏ tới khi có repo công khai (Thy duyệt 2026-10-08).
export function LandingCta() {
  return (
    <section data-screen-label="07 Final CTA" className="on-dark px-4 pb-8 sm:px-8">
      <div className="mx-auto flex max-w-[1136px] flex-col items-center gap-6 rounded-[20px] bg-dark-bg px-8 py-20 text-center text-dark-text">
        <BrandLogo variant="mark" height={52} alt="" />
        <h2 className="m-0 max-w-[760px] text-[clamp(32px,4vw,52px)] font-extrabold leading-[1.05] tracking-[-0.035em] [text-wrap:balance]">
          Every post, measured against its own channel.
        </h2>
        <p className="m-0 max-w-[600px] text-base leading-[1.6] text-dark-text-secondary [text-wrap:pretty]">
          The dashboard reads the same data as this page, with every topic and the method behind
          each number.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link
            href="/overview"
            className="flex h-12 items-center rounded-full bg-amber-on-dark px-[22px] text-[15px] font-bold text-text-primary"
          >
            View live dashboard
          </Link>
          <a
            href="#method"
            className="flex h-12 items-center rounded-full border border-white/28 bg-transparent px-[22px] text-[15px] font-medium text-dark-text"
          >
            See how it works
          </a>
        </div>
      </div>
    </section>
  );
}
