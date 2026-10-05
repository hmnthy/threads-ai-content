import { TopicExplorer } from "@/components/TopicExplorer";

export default function TopicsPage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-border-hairline px-6 py-5">
        <h1 className="text-[24px] font-semibold tracking-tight text-text-primary">Topic Explorer</h1>
        <p className="mt-1 text-sm text-text-secondary">
          What the channel writes about, discovered without predefined labels: multilingual sentence
          embeddings, reduced with UMAP and clustered with HDBSCAN.
        </p>
      </header>
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-6">
        <TopicExplorer />
      </main>
    </div>
  );
}
