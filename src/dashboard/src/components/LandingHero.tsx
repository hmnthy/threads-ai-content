import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

// Hero (Tầng B) — không lặp lại gradient band đã dùng ở Tầng A (design-system.md
// §13: "Cho gradient vào tầng A, đúng một lần — giữ cảm giác sang trọng mà không
// làm loãng"). Trọng tâm thị giác ở đây là typography lớn, nền phẳng.
export function LandingHero() {
  return (
    <section className="flex flex-col items-start gap-6 py-16 sm:py-20">
      <span className="rounded-full bg-amber-soft px-3 py-1 text-xs font-semibold text-amber-600">
        NLP/ML case study · live production data
      </span>
      <h1 className="max-w-3xl text-[40px] leading-[1.1] font-bold tracking-tight text-text-primary sm:text-[56px]">
        The algorithm, read back to you.
      </h1>
      <p className="max-w-2xl text-lg leading-relaxed text-text-secondary">
        Threads&apos; ranking algorithm is a black box — creators can&apos;t query why one post
        takes off and the next one doesn&apos;t. This project treats one real channel as a live
        case study: every number on this site is computed from a documented, cited formula, never
        a black-box score.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href="/overview"
          className="flex h-11 items-center gap-2 rounded-full bg-amber-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-amber-700"
        >
          View live dashboard
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
        <a
          href="#solution"
          className="flex h-11 items-center rounded-full border border-border-hairline px-5 text-sm font-medium text-text-secondary transition-colors hover:bg-bg-surface hover:text-text-primary"
        >
          See the methodology
        </a>
      </div>
    </section>
  );
}
