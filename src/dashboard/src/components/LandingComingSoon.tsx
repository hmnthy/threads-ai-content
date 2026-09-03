import { Sparkle } from "@phosphor-icons/react/dist/ssr";

// 1 khối riêng, nổi bật (không lẫn vào lưới tech stack) — đúng yêu cầu "AI
// Generative nên có 1 khối sẵn ghi Coming soon". Mô tả khớp đúng thiết kế RAG đã
// có trong docs/claude/data-model.md nhưng CHƯA xây (src/generation/ chưa tồn tại).
export function LandingComingSoon() {
  return (
    <section className="py-14">
      <div className="flex flex-col items-start gap-4 rounded-[20px] border border-border-hairline bg-bg-sunken p-8 sm:p-10">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-bg-surface text-text-muted">
          <Sparkle size={20} aria-hidden="true" />
        </div>
        <div className="flex items-center gap-2.5">
          <h2 className="text-xl font-bold tracking-tight text-text-muted">
            AI Content Generation
          </h2>
          <span className="rounded-full bg-bg-surface px-2.5 py-0.5 text-[11px] font-medium text-text-secondary">
            coming soon
          </span>
        </div>
        <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
          Not a generic AI voice: retrieval-augmented generation grounded on this channel&apos;s
          own highest-performing posts, in the author&apos;s own documented tone. Designed
          alongside the NLP pipeline above, reusing the same embeddings — not a bolt-on feature.
        </p>
      </div>
    </section>
  );
}
