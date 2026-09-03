interface StackItem {
  layer: string;
  tech: string;
  status: "live" | "coming soon";
  note: string;
}

// Grid 3 cột + badge status — tái dùng đúng pattern của MetricArchitectureGrid
// (Overview), không phát minh pattern mới cho landing. Nội dung khớp bảng "Tech
// Stack đã chốt" trong docs/claude/architecture.md, phân loại live/coming soon
// theo trạng thái THẬT của code (verify 2026-09-03, không phải kỳ vọng).
const STACK: StackItem[] = [
  { layer: "Backend / API", tech: "FastAPI", status: "live", note: "Sole backend — one language end to end, no Node.js API layer." },
  { layer: "Package manager", tech: "uv", status: "live", note: "Lockfile + venv management, replaces pip/poetry." },
  { layer: "Threads API client", tech: "httpx", status: "live", note: "Async, pairs naturally with FastAPI." },
  { layer: "Validation", tech: "Pydantic v2", status: "live", note: "Every API response and Threads payload is a typed model." },
  { layer: "AI / LLM", tech: "Claude API", status: "live", note: "Labels discovered topic clusters in English today; drafting content is the next layer." },
  { layer: "Dashboard", tech: "Next.js + Recharts", status: "live", note: "This site, deployed on Vercel." },
  { layer: "Database", tech: "SQLite", status: "live", note: "Dev database now; PostgreSQL planned before any multi-user use." },
  { layer: "Metric scoring", tech: "6-index architecture", status: "live", note: "Popularity / engagement / virality / conversation / velocity / longevity, kept separate." },
  { layer: "Language ID", tech: "lingua-py + Code-Mixing Index", status: "live", note: "Confidence-aware, built for short mixed-language text." },
  { layer: "NLP feature extraction", tech: "sentence-transformers (multilingual)", status: "live", note: "bge-m3 / multilingual-e5-large embeddings, no per-language tokenizer." },
  { layer: "Topic discovery", tech: "UMAP + HDBSCAN", status: "live", note: "Unsupervised clustering — see the Topic Explorer." },
  { layer: "Code quality", tech: "ruff, mypy (strict), pytest, pre-commit", status: "live", note: "Enforced on every commit, not just at the end." },
  { layer: "Fixed-category classification", tech: "SVM-RBF + Logistic Regression", status: "coming soon", note: "A supervised complement to the unsupervised clusters above — deferred, not started." },
  { layer: "Vector store / RAG", tech: "Chroma or FAISS", status: "coming soon", note: "Will reuse the embeddings already computed for clustering — no separate index yet." },
  { layer: "Image generation", tech: "Pillow + Google Sans font", status: "coming soon", note: "Carousel templates and font are ready; the generation code isn't written." },
];

export function LandingTechStack() {
  return (
    <section className="flex flex-col gap-6 py-14">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">Tech stack</h2>
        <p className="max-w-2xl text-text-secondary">
          Every layer of this project, shown as it actually stands today — nothing implied that
          isn&apos;t built yet.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {STACK.map((item) => (
          <div
            key={item.layer}
            className={`flex flex-col gap-2.5 rounded-xl border border-border-hairline p-5 ${
              item.status === "live" ? "bg-bg-card" : "bg-bg-sunken"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <span
                className={`text-[15px] font-semibold ${
                  item.status === "live" ? "text-text-primary" : "text-text-muted"
                }`}
              >
                {item.layer}
              </span>
              <span
                className={`flex-none rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                  item.status === "live" ? "bg-amber-soft text-amber-600" : "bg-bg-surface text-text-secondary"
                }`}
              >
                {item.status}
              </span>
            </div>
            <span className="font-mono text-[12.5px] text-text-secondary">{item.tech}</span>
            <span className="text-[13px] leading-snug text-text-muted">{item.note}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
