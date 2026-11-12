"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AnswerRow,
  Legend,
  LoadError,
  MethodSection,
  Section,
  SubSection,
  ToggleGroup,
  TYPE,
  UnitText,
  type KeyNumber,
} from "@/components/AppBlock";
import { getRagDemoFile } from "@/lib/api";
import { count } from "@/lib/landing";
import { goldAnswer, type GoldAnswer } from "@/lib/ragDemo/answer.ts";
import {
  LLM_MAX_SCORE,
  parseDemoFile,
  WAYS,
  type DemoFile,
  type Passage,
  type Question,
  type Unit,
  type Way,
} from "@/lib/ragDemo/demoFile.ts";
import { chunkParts, haikuKeeps } from "@/lib/ragDemo/filters.ts";
import { DEFAULT_PIPELINE, runPipeline, type PipelineResult } from "@/lib/ragDemo/pipeline.ts";
import { RRF_K } from "@/lib/ragDemo/fuse.ts";
import { TOP_N_DEFAULT, type Rerank } from "@/lib/ragDemo/rerank.ts";
import { buildWayIndex, type Retriever } from "@/lib/ragDemo/retrieve.ts";
import type { Row } from "@/lib/ragDemo/rank.ts";
import {
  characterCount,
  goldRankNote,
  goldUnitsSentence,
  nonGoldKept,
  showEmoji,
  THREADS_EMOJI,
  outcomeText,
  PIPELINE_STEPS,
  QUESTION_TESTS,
  STEP_STATUS_SHOWN,
  type StepStatus,
  quartiles,
  ragNumber,
  ragShort,
  rankText,
  RERANKS_SHOWN,
  RETRIEVERS_SHOWN,
  scoreName,
  WAYS_SHOWN,
} from "@/lib/ragPage";

// Trang /rag-pipeline bản đầu (Thy chốt 2026-11-12, phạm vi + lý do: `docs/design/ui-contract-audit.md`, mục
// "`/rag-pipeline` — trang bản đầu thu hẹp"; khối Loading thêm sau, phương án A; bản đồ pipeline thêm sau): 5 khối theo khuôn chung (Section → lựa chọn → câu trả lời + Key
// numbers → bằng chứng → Method and limits mở sẵn), chỉ component có sẵn của AppBlock. Engine chạy trong trình duyệt
// (`lib/ragDemo/`); các bước bản đầu chưa hiện giữ mặc định của `DEFAULT_PIPELINE` (không biến đổi câu hỏi, câu ngữ
// cảnh tắt, lọc và MMR tắt, top-N = 20, top-K = 10).

type Settings = { question: number; way: Way; retriever: Retriever; rerank: Rerank };

// Mặc định khi mở trang (ADR-0041): câu 1, recursive 500, hybrid RRF, chưa rerank
const START: Settings = {
  question: 1,
  way: DEFAULT_PIPELINE.way,
  retriever: DEFAULT_PIPELINE.retriever,
  rerank: DEFAULT_PIPELINE.rerank,
};

const K = DEFAULT_PIPELINE.topK;

// Ngôn ngữ gốc của 10 câu hỏi cố định (ADR-0037 D10: câu 6 tiếng Pháp, còn lại tiếng Việt)
function questionLanguage(question: Question): string {
  return question.number === 6 ? "French" : "Vietnamese";
}

function monthText(month: string): string {
  const [year, m] = month.split("-").map(Number);
  return new Date(Date.UTC(year, m - 1, 1)).toLocaleString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

// `provenance` khai báo `[key: string]: unknown` cho trường không thuộc engine: đọc có kiểm, không ép kiểu mù
function provenanceText(demo: DemoFile, read: (p: Record<string, unknown>) => unknown, fallback: string): string {
  const value = read(demo.provenance);
  return typeof value === "string" && value !== "" ? value : fallback;
}

// Bản dịch của một đoạn đến từ việc nào (`src/rag_demo/demo_file.py:266#_context_of`): đoạn là cả bài → việc
// `translate` (context null); đoạn khác → việc `context`, viết câu ngữ cảnh và dịch trong cùng một request
// (copy-reviewer vòng 3: nhãn phải ghi phiên bản prompt của đúng việc đã tạo ra bản dịch)
function translationJob(passage: { context: string | null }): "translate" | "context" {
  return passage.context === null ? "translate" : "context";
}

function promptVersion(demo: DemoFile, job: "rerank" | "translate" | "context"): string {
  return provenanceText(
    demo,
    (p) => (p.prompt_versions as Record<string, unknown> | undefined)?.[job],
    "not recorded",
  );
}

// Câu vai trò: 2 việc dịch cùng phiên bản → ghi một số; khác nhau → ghi rõ việc nào cho đoạn nào
function translationVersions(demo: DemoFile): string {
  const whole = promptVersion(demo, "translate");
  const other = promptVersion(demo, "context");
  return whole === other
    ? `prompt version ${whole}`
    : `prompt version ${whole} for whole content units, ${other} for other passages, translated together with their context sentence`;
}

function rerankPromptVersion(demo: DemoFile): string {
  return promptVersion(demo, "rerank");
}

// Số content unit lúc đóng băng (ADR-0037 D2: 20; ADR-0040 bỏ 1 bài bị xoá) — file demo không ghi số này
const FROZEN_UNITS = 20;

function partText(parts: readonly string[]): string {
  if (parts.length > 1) return "spans the opening post and a follow-up post";
  return parts[0] === "opening" ? "opening post" : "follow-up post";
}

export function RagPipelineView() {
  const [demo, setDemo] = useState<DemoFile | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [settings, setSettings] = useState<Settings>(START);

  useEffect(() => {
    let alive = true;
    getRagDemoFile()
      .then((raw) => {
        if (alive) setDemo(parseDemoFile(raw));
      })
      .catch((err: unknown) => {
        // Chi tiết ở console; người xem thấy câu + nút thử lại (LoadError)
        console.error("rag-pipeline: could not load the demo file", err);
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [attempt]);

  // Index BM25 dựng lại chỉ khi đổi cách chia (thống kê của cả kho, câu ngữ cảnh tắt ở bản đầu)
  const index = useMemo(() => (demo ? buildWayIndex(demo, settings.way, false) : null), [demo, settings.way]);
  const question = demo?.questions.find((q) => q.number === settings.question) ?? null;
  const result = useMemo(() => {
    if (!demo || !index || !question) return null;
    const config = { ...DEFAULT_PIPELINE, way: settings.way, retriever: settings.retriever, rerank: settings.rerank };
    return runPipeline(demo, index, { question }, config);
  }, [demo, index, question, settings.way, settings.retriever, settings.rerank]);

  if (failed) {
    return (
      <LoadError
        what="The demo data could not be loaded right now."
        onRetry={() => {
          setFailed(false);
          setAttempt((value) => value + 1);
        }}
      />
    );
  }
  if (!demo || !question || !result) {
    return (
      <div className="flex flex-col gap-10" aria-busy="true" aria-label="Loading the demo data">
        <div className="h-[320px] motion-safe:animate-pulse rounded-xl bg-bg-surface" />
        <div className="h-[640px] motion-safe:animate-pulse rounded-xl bg-bg-surface" />
      </div>
    );
  }

  const gold = goldAnswer(question, result);
  const update = (patch: Partial<Settings>) => setSettings((current) => ({ ...current, ...patch }));
  return (
    <div className="flex flex-col gap-10">
      <PipelineMapBlock />
      <LoadingBlock demo={demo} />
      <QuestionBlock demo={demo} question={question} onPick={(n) => update({ question: n })} />
      <PassagesBlock demo={demo} question={question} settings={settings} result={result} gold={gold} update={update} />
      <AboutBlock demo={demo} />
    </div>
  );
}

function QuestionBlock({
  demo,
  question,
  onPick,
}: {
  demo: DemoFile;
  question: Question;
  onPick: (n: number) => void;
}) {
  return (
    <Section
      id="question"
      n={ragNumber("question")}
      short={ragShort("question")}
      title="Pick a question"
      purpose={`Each of the ${demo.questions.length} fixed questions is built around one known difficulty for retrieval. On these ${demo.units.length} content units, some of those difficulties never push the answer out of first place.`}
    >
      {/* UI-0037-static-precomputed: câu hỏi cố định có nhãn "precomputed" */}
      <Control label="Fixed questions · precomputed">
        <ToggleGroup
          label="Question"
          mono
          options={demo.questions.map((q) => ({ key: String(q.number), label: `Q${q.number}` }))}
          value={String(question.number)}
          onChange={(key) => onPick(Number(key))}
        />
      </Control>
      <AnswerRow
        answer={`Q${question.number}: ${question.english}`}
        points={[
          `**Original wording** (${questionLanguage(question)}, the text every step searches with): “${question.text}”`,
          `**What it tests:** ${QUESTION_TESTS[question.number]}.`,
          `**Correct answer:** ${goldUnitsSentence(question)} It was fixed by post id before any retrieval ran, so no score decides it.`,
        ]}
      />
      <MethodSection
        steps={[
          {
            title: "Fixed questions",
            plain:
              "The questions and their correct content units were chosen before anything was retrieved. The questions are marked “precomputed”: their model scores (dense similarity, cross-encoder, Claude Haiku) were computed once in advance and stored in the demo file; your browser only ranks and sorts.",
          },
          {
            title: "English line",
            plain:
              "The English question above is a translation for reading. Retrieval and every model score use the original wording.",
          },
        ]}
        limits={[
          "Ten questions show mechanisms, one each; they are not a test set, so the page computes no accuracy from them.",
          "This version has no box to type your own question.",
        ]}
      />
    </Section>
  );
}

function PassagesBlock({
  demo,
  question,
  settings,
  result,
  gold,
  update,
}: {
  demo: DemoFile;
  question: Question;
  settings: Settings;
  result: PipelineResult;
  gold: GoldAnswer | null;
  update: (patch: Partial<Settings>) => void;
}) {
  const total = demo.ways[settings.way].length;
  const ranked = result.final ?? [];
  const shown = result.cut ? ranked.slice(0, result.cut.shown) : [];
  const goldChunks = new Set(Object.values(question.gold_chunks[settings.way]).flat());
  // Số dòng thật đang hiện: nhóm hoà vắt mốc K hiện cả nhóm (> K), danh sách ngắn hơn K (< K) — ux-reviewer vòng 1
  const shownNote =
    shown.length > K
      ? `The first ${K} (a design choice), plus ${shown.length - K} tied with the ${K}th.`
      : shown.length < K
        ? `Only ${shown.length} passages were ranked, fewer than the ${K} the page shows (a design choice).`
        : `The first ${K} of the ranked list (a design choice).`;
  const keyNumbers: KeyNumber[] = [
    {
      value: gold && gold.main.kind === "rank" ? rankText(gold.main.from, gold.main.to) : "—",
      label: "Correct answer rank",
      note: goldRankNote(question, K),
    },
    {
      value: count(ranked.length),
      label: "Passages ranked",
      share: { part: ranked.length, whole: total, of: `${count(total)} passages` },
      note: "BM25 leaves out passages that share no word with the question; dense similarity ranks every passage.",
    },
    { value: count(shown.length), label: "Passages shown", note: shownNote },
  ];
  return (
    <Section
      id="passages"
      n={ragNumber("passages")}
      short={ragShort("passages")}
      title="Where the answer lands"
      purpose="Choose how the content units are cut into passages, how passages are retrieved and whether they are reranked; the ranking below updates at once."
    >
      <div className="flex flex-col gap-5">
        <Control label="Chunking (how content units are cut into passages)">
          <ToggleGroup
            label="Chunking"
            options={WAYS.map((way) => ({ key: way, label: WAYS_SHOWN[way].label }))}
            value={settings.way}
            onChange={(way) => update({ way })}
          />
          <p className={`m-0 ${TYPE.note}`}>
            {WAYS_SHOWN[settings.way].sentence} {count(total)} passages from {count(demo.units.length)} content units.
          </p>
        </Control>
        <Control label="Retrieval (how passages are found)">
          <ToggleGroup
            label="Retrieval"
            options={(["bm25", "dense", "hybrid"] as const).map((key) => ({ key, label: RETRIEVERS_SHOWN[key] }))}
            value={settings.retriever}
            onChange={(retriever) => update({ retriever })}
          />
        </Control>
        <Control label={`Reranking (rescoring the top ${TOP_N_DEFAULT} passages)`}>
          <ToggleGroup
            label="Reranking"
            options={(["none", "cross_encoder", "haiku"] as const).map((key) => ({ key, label: RERANKS_SHOWN[key] }))}
            value={settings.rerank}
            onChange={(rerank) => update({ rerank })}
          />
        </Control>
      </div>
      <AnswerRow
        answer={answerSentence(question, gold)}
        points={unitPoints(question, gold)}
        keyNumbers={keyNumbers}
        below={
          <div className="flex flex-col gap-4">
            {/* UI-0041-stable-rerank-ties cột E: câu ngắn cạnh kết quả rerank Haiku */}
            {settings.rerank === "haiku" ? (
              <p className={`m-0 ${TYPE.body}`}>
                Claude Haiku scores are whole numbers from 0 to 3, so many passages share a score. Equal Haiku scores keep the order
                of the retrieval step, so two setups with different retrieval can order the same Haiku scores differently.
              </p>
            ) : null}
            <PassageLegend rerank={settings.rerank} />
            {shown.length === 0 ? (
              <p className={`m-0 ${TYPE.body}`}>No passage shares a word with this question, so BM25 returns nothing.</p>
            ) : (
              <ol className="m-0 flex list-none flex-col p-0">
                {shown.map((row, i) => (
                  <PassageRow
                    key={row.chunk}
                    demo={demo}
                    way={settings.way}
                    row={row}
                    position={i + 1}
                    retriever={settings.retriever}
                    rerank={settings.rerank}
                    isGold={goldChunks.has(row.chunk)}
                  />
                ))}
              </ol>
            )}
          </div>
        }
      />
      <MethodSection
        steps={[
          {
            title: "Chunking",
            plain:
              "Each content unit is cut into passages by the chosen method. Fixed windows overlap by about 40, 60 or 100 characters (roughly an eighth of the window), so the words just before a cut also start the next window.",
          },
          {
            title: "BM25",
            plain:
              "Scores a passage by the question words it contains, giving more weight to rare words and less to long passages. Words are Vietnamese syllables; a question typed without diacritics is matched against passages with diacritics removed.",
            formula: [
              "score(q, d) = Σ_(t ∈ q) IDF(t) · f(t, d) ÷ (f(t, d) + k_1 · (1 − b + b · |d| ÷ avgdl))",
              "IDF(t) = ln(1 + (N − n(t) + 0.5) ÷ (n(t) + 0.5))",
              "f(t, d): count of word t in passage d · |d|: passage length in words · avgdl: average length · N: passages · n(t): passages containing t · k_1 = 1.2, b = 0.75 (Lucene defaults; Lucene’s form, without the (k_1 + 1) factor, which does not change the order)",
            ],
          },
          {
            title: "Dense similarity",
            plain:
              "The question and each passage are turned into vectors by OpenAI text-embedding-3-small; passages close in meaning score high even with no shared word.",
            formula: ["cos(q, d) = (q · d) ÷ (‖q‖ ‖d‖)"],
          },
          {
            title: "Hybrid (reciprocal rank fusion, RRF)",
            plain:
              `Gives a passage 1 ÷ (${RRF_K} + its rank) in the BM25 list and in the dense list, and adds the two, so a passage near the top of either list rises. Only ranks are used, not raw scores, because the two scores are on different scales.`,
            formula: [
              "RRF(d) = Σ_(lists) 1 ÷ (k + r(d))",
              `k = ${RRF_K} (Cormack et al., 2009) · r(d): rank of passage d in that list (tied passages get their average rank); a passage missing from a list adds nothing`,
            ],
          },
          {
            title: "Cross-encoder reranking",
            plain: `Rereads the question and each of the top ${TOP_N_DEFAULT} passages together with BAAI/bge-reranker-v2-m3 and sorts them by its score (a raw logit: higher means more relevant). Passages below the top ${TOP_N_DEFAULT} keep their order and are marked “not reranked”.`,
          },
          {
            title: "Claude Haiku reranking",
            plain: `Claude Haiku 5.5 (prompt version ${rerankPromptVersion(demo)}) gave each question–passage pair a score from 0 (unrelated) to 3 (answers the question); 2 or more is labelled “keep”. Equal scores keep the order of the step before, so two setups can rank the same passages differently.`,
          },
          {
            title: "Ranks and ties",
            plain:
              "Scores are rounded to 6 decimals. Passages with equal rounded scores are tied: they share a rank range, shown as “3–4”, because no single order between them is more correct. Claude Haiku reranking is the exception: equal Haiku scores keep the order of the step before, so they get separate ranks unless they were already tied there.",
          },
        ]}
        limits={[
          "Both rerankers score the original question only.",
          "The cross-encoder is run with a limit of 1,024 tokens per question–passage pair (a setting; the model accepts more); every pair in this demo fits, so nothing is cut.",
          "With 19 content units, a different setup often moves the answer by only a few ranks; the page shows mechanisms, not which setup is best.",
        ]}
      />
    </Section>
  );
}

function Control({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className={TYPE.th}>{label}</span>
      {children}
    </div>
  );
}

function answerSentence(question: Question, gold: GoldAnswer | null): string {
  if (gold === null) {
    return `No content unit answers Q${question.number}, so there is no correct passage to rank. The list shows what retrieval returns anyway: the top passage is only the closest match.`;
  }
  const where = outcomeText(gold.main, K);
  return question.rule === "both"
    ? `The answer needs 2 content units; the later one to appear is at ${where}.`
    : `The correct answer is at ${where}.`;
}

function unitPoints(question: Question, gold: GoldAnswer | null): ReactNode[] {
  if (gold === null || question.gold_unit_ids.length < 2) return [];
  return question.gold_unit_ids.map(
    (unit, i) => `**Content unit ${i + 1} of the answer:** ${outcomeText(gold.units[unit], K)}.`,
  );
}

function PassageLegend({ rerank }: { rerank: Rerank }) {
  const items = [
    { mark: <Mark>★</Mark>, name: "Correct answer", rule: "the passage belongs to the answer’s content unit (for Q5 and Q8, it also covers the answering part)." },
    {
      mark: <Mark>=</Mark>,
      name: "Tied",
      rule:
        rerank === "haiku"
          ? "equal score after rounding; the rank is a range. Equal Haiku scores are tied only if they were already tied before reranking."
          : "equal score after rounding; the rank is a range.",
    },
  ];
  if (rerank !== "none") {
    items.push({ mark: <Mark>·</Mark>, name: "Not reranked", rule: `outside the top ${TOP_N_DEFAULT}; it keeps its rank and score from retrieval.` });
  }
  if (rerank === "haiku") {
    items.push({ mark: <Mark>✓</Mark>, name: "Keep / drop", rule: "Haiku score 2 or more is “keep”, below 2 is “drop”; the label does not remove the passage." });
  }
  return <Legend items={items} />;
}

function Mark({ children }: { children: ReactNode }) {
  return (
    <span aria-hidden="true" className="font-mono text-[12.5px] font-semibold text-amber-700">
      {children}
    </span>
  );
}

function PassageRow({
  demo,
  way,
  row,
  position,
  retriever,
  rerank,
  isGold,
}: {
  demo: DemoFile;
  way: Way;
  row: Row;
  position: number;
  retriever: Retriever;
  rerank: Rerank;
  isGold: boolean;
}) {
  const chunk = demo.ways[way][row.chunk];
  const passage = demo.passages[chunk.passage];
  const unit = demo.units.find((u) => u.id === chunk.unit)!;
  const tied = row.tiedFrom < row.tiedTo;
  const labels = [
    isGold ? "★ correct answer" : null,
    tied ? "= tied" : null,
    position > K ? "tied across the cut" : null,
    row.notReranked && rerank !== "none" ? "· not reranked" : null,
    rerank === "haiku" && !row.notReranked ? (haikuKeeps(row.score) ? "✓ keep" : "✗ drop") : null,
  ].filter((label): label is string => label !== null);
  return (
    <li className="grid grid-cols-1 gap-3 border-t border-border-hairline py-5 first:border-t-0 sm:grid-cols-[96px_minmax(0,1fr)] sm:gap-6">
      <div className="flex flex-row items-baseline gap-3 sm:flex-col sm:gap-1">
        <span className={`${TYPE.mono} font-semibold text-text-primary`}>rank {rankText(row.tiedFrom, row.tiedTo)}</span>
        <span className={`${TYPE.mono} text-text-secondary`}>{row.score.toFixed(6)}</span>
        <span className={TYPE.label}>{scoreName(retriever, rerank, row.notReranked)}</span>
        {/* UI-0037-static-precomputed: điểm Haiku là kết quả LLM → ghi model + phiên bản prompt (code-reviewer vòng 1) */}
        {rerank === "haiku" && !row.notReranked ? (
          <span className={TYPE.label}>prompt version {promptVersion(demo, "rerank")}</span>
        ) : null}
      </div>
      <div className="flex min-w-0 flex-col gap-2">
        <span className={TYPE.label}>
          {monthText(unit.month)} · {partText(chunkParts(demo, way, row.chunk))}
          {labels.length > 0 ? ` · ${labels.join(" · ")}` : ""}
        </span>
        <PassageText demo={demo} passage={passage} unit={unit} />
      </div>
    </li>
  );
}

// Chữ một đoạn: bản dịch tiếng Anh trước (kèm model + phiên bản prompt), rồi chữ gốc có dòng "Topic … · original
// language" (UnitText) — một cách hiện cho khối Loading và danh sách xếp hạng
function PassageText({ demo, passage, unit }: { demo: DemoFile; passage: Passage; unit: Unit }) {
  return (
    <>
      <span className="flex flex-col gap-0.5">
        {/* UI-0037-static-precomputed: mỗi kết quả LLM ghi tên model + phiên bản prompt */}
        <span className={TYPE.label}>
          English (machine translation by Claude Haiku 5.5, prompt version {promptVersion(demo, translationJob(passage))})
        </span>
        <span className={`${TYPE.body} text-text-primary`}>{showEmoji(passage.en)}</span>
      </span>
      <UnitText text={showEmoji(passage.text)} topic={unit.topic.id === null ? null : unit.topic.label_en} />
    </>
  );
}

// Bản đồ pipeline (Thy chốt 2026-11-12, sau khi hỏi "đã so với chuẩn của thầy chưa?"): đủ các bước của repo mẫu theo
// đúng số + tên, mỗi bước ghi trạng thái trên trang bản đầu và khối chứa nó — người quen chuẩn dò được bước nào ở đâu
function PipelineMapBlock() {
  const counts = (status: StepStatus) => PIPELINE_STEPS.filter((step) => step.status === status).length;
  // số ít / số nhiều theo số đếm (code-reviewer: câu không được viết cứng theo số hôm nay)
  const verb = (n: number, one: string, many: string) => (n === 1 ? one : many);
  const stages = [
    { key: "indexing", title: "Stage 1 — Indexing", note: "Prepares the content units so they can be searched; run once, before any question." },
    { key: "generation", title: "Stage 2 — Generation", note: "Runs for each question: find, rerank, then (in a full RAG system) write an answer." },
  ] as const;
  return (
    <Section
      id="pipeline"
      n={ragNumber("pipeline")}
      short={ragShort("pipeline")}
      title="The pipeline, step by step"
      purpose="Every step of a standard RAG pipeline, numbered as in the reference project this page follows, and where each one is on this page."
    >
      <AnswerRow
        answer={`Of the ${PIPELINE_STEPS.length} steps, ${counts("on-page")} can be changed on this page, ${counts("fixed")} ${verb(counts("fixed"), "runs", "run")} with a fixed choice and ${verb(counts("fixed"), "is", "are")} shown or explained, ${counts("later")} ${verb(counts("later"), "is", "are")} planned for a later version, and ${counts("left-out")} ${verb(counts("left-out"), "is", "are")} left out on purpose: this demo ranks source passages and writes no answer.`}
        below={
          <div className="flex flex-col gap-6">
            <Legend
              items={(Object.keys(STEP_STATUS_SHOWN) as StepStatus[]).map((status) => ({
                mark: <Mark>{STEP_STATUS_SHOWN[status].mark}</Mark>,
                name: STEP_STATUS_SHOWN[status].name,
                rule: STEP_STATUS_SHOWN[status].rule,
              }))}
            />
            {stages.map((stage) => (
              <SubSection key={stage.key} title={stage.title} note={stage.note}>
                <ol className="m-0 flex list-none flex-col p-0">
                  {PIPELINE_STEPS.filter((step) => step.stage === stage.key).map((step) => {
                    const status = STEP_STATUS_SHOWN[step.status];
                    return (
                      <li
                        key={step.number}
                        className="grid grid-cols-[40px_minmax(0,1fr)] gap-3 border-t border-border-hairline py-4 first:border-t-0"
                      >
                        <span className={`${TYPE.mono} font-semibold text-amber-600`}>{step.number}</span>
                        <div className="flex min-w-0 flex-col gap-1">
                          <span className={TYPE.bodyStrong}>
                            {step.name}
                            {step.optional ? <span className={`${TYPE.note} font-normal`}> · optional</span> : null}
                          </span>
                          <span className={`${TYPE.note} flex flex-wrap items-baseline gap-x-1.5`}>
                            <Mark>{status.mark}</Mark>
                            <span className="font-semibold text-text-primary">{status.name}</span>
                            {step.block ? (
                              <>
                                <span aria-hidden="true">·</span>
                                <a href={`#${step.block}`} className="font-medium text-amber-700 underline underline-offset-4">
                                  {ragNumber(step.block)} {ragShort(step.block)}
                                </a>
                              </>
                            ) : null}
                          </span>
                          <p className={`m-0 ${TYPE.body}`}>{step.what}</p>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </SubSection>
            ))}
          </div>
        }
      />
      <MethodSection
        steps={[
          {
            title: "Reference",
            plain:
              "The steps, their order and their numbers follow the README of the open-source RAG-pipeline-visualizer (vietnh1009), which this page credits; that project has no steps 5 and 6. Its Stage 2 is called Generation because a full RAG system ends by writing an answer.",
          },
        ]}
        limits={[
          "The reference project lets you pick among many tools at each step (several PDF loaders and vector databases, for example); this demo has one source and precomputed scores, so its choices are narrower.",
          "Steps 10 and 11 are left out by design: this page is kept to ranked passages so retrieval can be seen directly; answering questions belongs to a separate assistant, built only after a knowledge base passes its quality checks.",
        ]}
      />
    </Section>
  );
}

// Khối Loading (Thy chốt 2026-11-12, phương án A — bước đầu của pipeline trong repo mẫu): nguồn, cách ghép một content
// unit, mốc đóng băng, làm sạch; chọn một content unit để xem nó tách thành từng post. Bản dịch theo post lấy từ đoạn
// của cách chia "post": đo 2026-11-12, 19/19 bài có đoạn trùng khít vị trí từng post (63 post)
function LoadingBlock({ demo }: { demo: DemoFile }) {
  const [picked, setPicked] = useState(0);
  const units = demo.units;
  const posts = units.reduce((sum, unit) => sum + unit.posts.length, 0);
  const followUps = posts - units.length;
  const lengths = units.map((unit) => characterCount(unit.text));
  const spread = quartiles(lengths);
  const months = [...new Set(units.map((unit) => unit.month))].sort();
  const monthCounts = months.map((month) => `${units.filter((u) => u.month === month).length} from ${monthText(month)}`);
  const unit = units[Math.min(picked, units.length - 1)];
  const postChunks = demo.ways.post.filter((chunk) => chunk.unit === unit.id).sort((a, b) => a.start - b.start);
  return (
    <Section
      id="loading"
      n={ragNumber("loading")}
      short={ragShort("loading")}
      title="Load the content units"
      purpose="Where the text comes from and how one Threads thread becomes one content unit, before anything is cut into passages."
    >
      <AnswerRow
        answer={`${count(units.length)} content units were loaded, ${count(posts)} posts in all: each content unit is an opening post plus the follow-up posts its author added in the same thread.`}
        points={[
          "**Source:** the Threads API (Meta’s official interface) returns the author’s posts and replies; a scheduled job stores them in a SQLite database every 4 hours, and this demo reads a frozen copy.",
          // ADR-0004 quyết định 1 (`src/processing/thread_reconstruction.py:49#reaches_root`): mọi mắt xích là post của tác
          // giả — code-reviewer + copy-reviewer: câu "lần ngược về post mở đầu" thiếu điều kiện này là luật lỏng cũ
          "**One thread, one content unit:** a follow-up post is a reply by the author whose chain of “replied to” links reaches the opening post through the author’s own posts only. Comments from other people, and the author’s answers to them, are left out.",
          `**Frozen:** the channel’s ${FROZEN_UNITS} most recent content units on Nov 5, 2026, each locked by its id, length and a SHA-256 hash. The author later deleted one of them from Threads, so ${count(units.length)} remain; before each publish the text is checked against Threads again.`,
          `**Text only, in its original form:** images and videos are not read, and the text keeps its case and its Vietnamese diacritics. Emoji that exist only on Threads come back from the API as the character ${THREADS_EMOJI} (checked against the Threads app on one post), so the page shows them as **[emoji]**.`,
        ]}
        keyNumbers={[
          { value: count(units.length), label: "Content units", note: `${monthCounts.join(", ")} (month of the opening post, Paris time).` },
          {
            value: count(followUps),
            label: "Follow-up posts",
            share: { part: followUps, whole: posts, of: `${count(posts)} posts` },
            note: `${count(units.filter((u) => u.posts.length > 1).length)} of ${count(units.length)} content units have at least one.`,
          },
          {
            value: count(Math.round(spread.median)),
            label: "Characters per content unit (median)",
            note: `Middle half ${count(Math.round(spread.q1))}–${count(Math.round(spread.q3))} (IQR), n = ${count(units.length)}.`,
          },
        ]}
        below={
          <div className="flex flex-col gap-4">
            <Control label="Inspect one content unit">
              <ToggleGroup
                label="Content unit"
                mono
                // "#1" thay "1": nút 1 chữ số hẹp hơn vùng chạm 44px (máy đo C4); không sửa kiểu ToggleGroup dùng chung
                options={units.map((_, i) => ({ key: String(i), label: `#${i + 1}` }))}
                value={String(picked)}
                onChange={(key) => setPicked(Number(key))}
              />
            </Control>
            <p className={`m-0 ${TYPE.note}`}>
              {monthText(unit.month)} · {unit.posts.length === 1 ? "1 post" : `${unit.posts.length} posts`} ·{" "}
              {count(characterCount(unit.text))} characters
            </p>
            <ol className="m-0 flex list-none flex-col p-0">
              {postChunks.map((chunk, i) => (
                <li
                  key={chunk.id}
                  className="flex flex-col gap-2 border-t border-border-hairline py-5 first:border-t-0"
                >
                  <span className={`${TYPE.mono} font-semibold text-text-primary`}>
                    post {i + 1} · {i === 0 ? "opening post" : "follow-up post"}
                  </span>
                  <PassageText demo={demo} passage={demo.passages[chunk.passage]} unit={unit} />
                </li>
              ))}
            </ol>
          </div>
        }
      />
      <MethodSection
        steps={[
          {
            title: "Collect",
            plain:
              "A scheduled job reads the author’s posts and replies from the Threads API and stores them in SQLite, about every 4 hours while the author’s laptop is on.",
          },
          {
            title: "Assemble",
            plain:
              "Each reply carries a link to the post it answers. A reply is a follow-up post only if every link back to the opening post goes through the author’s own posts; a reply under someone else’s comment is not. The content unit’s text is the opening post and its follow-ups, in reading order, joined with a space.",
          },
          {
            title: "Freeze",
            plain: `The ${FROZEN_UNITS} most recent content units on Nov 5, 2026 were fixed by id, length and SHA-256 hash, so every later step reads the same text. Before each publish, a check compares them with Threads and stops if one was deleted or edited.`,
          },
        ]}
        limits={[
          "Only the text of the posts is used: images and videos are not read.",
          "Comments from other people are not stored at all.",
          "A post edited on Threads after the freeze is not updated here; the publish check stops instead, and the author decides.",
        ]}
      />
    </Section>
  );
}

function AboutBlock({ demo }: { demo: DemoFile }) {
  const partly = nonGoldKept(demo, LLM_MAX_SCORE);
  const pairs = `${count(demo.questions.length)} questions × ${count(demo.passages.length)} distinct passages from all ${WAYS.length} chunking methods`;
  const embedding = provenanceText(demo, (p) => p.embedding_model, "text-embedding-3-small");
  const crossEncoder = provenanceText(
    demo,
    (p) => (p.cross_encoder as Record<string, unknown> | undefined)?.model,
    "BAAI/bge-reranker-v2-m3",
  );
  return (
    <Section
      id="about"
      n={ragNumber("about")}
      short={ragShort("about")}
      title="What this demo is, and is not"
      purpose="Which models were used, and what the numbers on this page can and cannot tell."
    >
      <AnswerRow
        answer={`An illustration of how retrieval steps behave, not an evaluation: ${demo.units.length} content units and ${demo.questions.length} questions are far too few to say which setup is best.`}
        points={[
          `**The correct answers stay as fixed in advance.** Claude Haiku rated ${count(partly.total)} of ${count(partly.pairs)} question–passage pairs 2 or more (“partly answers” or better) although the passage is not in the fixed answer${partly.top === 0 ? `; none was rated ${LLM_MAX_SCORE}` : `; ${count(partly.top)} were rated ${LLM_MAX_SCORE}`}. Some do answer in part, others are Haiku mistakes. They are still not marked ★ correct answer.`,
          "**English text is machine translation.** Dish and brand names stay in Vietnamese, and a passage that starts mid-sentence sometimes keeps a few Vietnamese words.",
          <>
            <strong className="font-semibold text-text-primary">Credit:</strong> the page follows the structure of the open-source{" "}
            <a
              href="https://github.com/vietnh1009/RAG-pipeline-visualizer"
              className="font-medium text-amber-700 underline underline-offset-4"
              rel="noopener noreferrer"
              target="_blank"
            >
              RAG-pipeline-visualizer
            </a>{" "}
            by vietnh1009; the code here is written from scratch.
          </>,
        ]}
        keyNumbers={[
          { value: count(demo.questions.length), label: "Questions", note: "Fixed in advance, each with its correct content units." },
          {
            value: count(partly.total),
            label: "Extra “partly answers”",
            note: `Question–passage pairs outside the fixed answers that Claude Haiku rated 2 or more, out of ${count(partly.pairs)} (${pairs}).`,
          },
        ]}
      />
      <MethodSection
        steps={[
          {
            title: "Computed in advance",
            // code-reviewer + copy-reviewer vòng 3: file không chứa vector, chỉ điểm cosine đã tính sẵn
            plain: `Computed once in advance and stored in one file: the similarity between every question and every passage, from OpenAI ${embedding} vectors (made through its API; the vectors themselves are not in the file), cross-encoder scores for every question–passage pair (${crossEncoder}, run on a laptop GPU), and Claude Haiku 5.5 outputs (through Anthropic’s API). Your browser downloads that file and runs BM25, fusion and sorting itself.`,
          },
          {
            title: "Claude Haiku’s roles",
            // code-reviewer vòng 1: file còn câu ngữ cảnh + câu hỏi biến đổi (gồm HyDE) do Haiku viết — nói rõ trang chưa dùng
            plain: `On this page, Claude Haiku 5.5 plays two roles: translating every passage for reading (${translationVersions(demo)}) and scoring every question–passage pair from 0 to 3 (prompt version ${rerankPromptVersion(demo)}). The demo file also holds context sentences and question rewrites it wrote for later versions of this page; none of them is shown or used here. It never writes the final answer: the page only ranks passages from the channel.`,
          },
        ]}
        limits={[
          "A model score is stored once and never re-run, so the page always shows the same numbers for the same setup.",
          "The frozen content units are not updated by the scheduled data jobs; the rest of the dashboard is.",
        ]}
      />
    </Section>
  );
}
