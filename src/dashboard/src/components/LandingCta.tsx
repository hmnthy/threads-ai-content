import Link from "next/link";
import { TYPE } from "@/lib/typeScale";

// Khối CTA cuối trên dải tối (design-system §2.6, §7). Không logo (Thy 2026-11-01: viền trắng của logo lộ trên nền tối).
// Nút 2 dẫn /topics — mời một bước mới thay vì đưa ngược lên sơ đồ (Thy 2026-11-01, ADR-0032); nút repo bỏ tới khi
// Thy quyết (Thy duyệt 2026-10-08).
export function LandingCta() {
  return (
    <section data-screen-label="07 Final CTA" className="on-dark px-4 pb-8 sm:px-8">
      <div className="mx-auto flex max-w-[1136px] flex-col items-center gap-6 rounded-[20px] bg-dark-bg px-8 py-20 text-center text-dark-text">
        <h2 className="m-0 max-w-[760px] text-[clamp(32px,3.6vw,46px)] font-extrabold leading-[1.08] tracking-[-0.035em] [text-wrap:balance]">
          Every content unit, measured against its own channel.
        </h2>
        <p className="m-0 max-w-[640px] text-[18px] leading-[1.6] text-dark-text-secondary [text-wrap:pretty]">
          The dashboard reads the same data as this page, with every topic and the method behind
          each number.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link
            href="/overview"
            className={`flex h-12 items-center rounded-full bg-amber-on-dark px-[22px] ${TYPE.cta} text-text-primary`}
          >
            View live dashboard
          </Link>
          {/* Nút 2 mời một bước mới, không đưa ngược lên sơ đồ vừa đọc (Thy 2026-11-01) */}
          <Link
            href="/topics"
            className={`flex h-12 items-center rounded-full border border-white/28 bg-transparent px-[22px] ${TYPE.cta} text-dark-text`}
          >
            Explore all topics
          </Link>
        </div>
      </div>
    </section>
  );
}
