import Image from "next/image";

// Bio DRAFT — chỉ dựa trên fact đã có trong CLAUDE.md (kênh "thydilammuon",
// người Việt tại Pháp, nội dung alternance/xin việc/lifestyle). KHÔNG bịa chi
// tiết cá nhân nào khác. Cần user duyệt/sửa lại trước khi coi là bản cuối.
export function LandingAuthor() {
  return (
    <section className="flex flex-col gap-6 py-14 sm:flex-row sm:items-center sm:gap-10">
      <div className="h-24 w-24 flex-none overflow-hidden rounded-full border border-border-hairline bg-bg-surface">
        <Image
          src="/photo-author.jpg"
          alt="Thy, author of the thydilammuon Threads channel"
          width={96}
          height={96}
          className="h-full w-full object-cover"
          style={{ transform: "scale(1.75)", transformOrigin: "50% 34%" }}
        />
      </div>
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-bold tracking-tight text-text-primary">About the channel</h2>
        <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
          Built by Thy (@thydilammuon), a Vietnamese creator living and working in France who
          posts about alternance, job hunting, and everyday life as an expat. This project started
          as a way to actually understand her own channel — not vanity metrics, but a rigorous
          look at what her real posts do — and grew into the full statistics + NLP case study on
          this site.
        </p>
      </div>
    </section>
  );
}
