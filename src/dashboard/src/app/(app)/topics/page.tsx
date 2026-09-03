import { TopicExplorer } from "@/components/TopicExplorer";

export default function TopicsPage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-bg-border px-6 py-5">
        <h1 className="text-[24px] font-semibold tracking-tight text-text-primary">Topic Explorer</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Unsupervised topic clusters discovered from the channel&apos;s posts (UMAP 3D + HDBSCAN).
        </p>
      </header>
      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-6">
        <TopicExplorer />
      </main>
    </div>
  );
}
