"use client";

import { Fragment, useEffect, useMemo, useState, type ReactNode } from "react";
import { CaretDown } from "@phosphor-icons/react";
import {
  AnswerRow,
  ControlLabel,
  H,
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
import { MIX_MAX, MIX_MIN } from "@/components/PostingTimeHeatmap";
import { TermGroups, type TermGroup } from "@/components/TermGlossary";
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
import { chunkParts, cosineOf, haikuKeeps } from "@/lib/ragDemo/filters.ts";
import { DEFAULT_PIPELINE, runPipeline, type PipelineResult } from "@/lib/ragDemo/pipeline.ts";
import { RRF_K } from "@/lib/ragDemo/fuse.ts";
import { TOP_N_DEFAULT, type Rerank } from "@/lib/ragDemo/rerank.ts";
import { buildWayIndex, contextEffective, type Retriever } from "@/lib/ragDemo/retrieve.ts";
import type { Row } from "@/lib/ragDemo/rank.ts";
import {
  answerSentence,
  characterCount,
  chunkingAnswer,
  chunkStats,
  CONTEXT_SHOWN,
  cosinePairs,
  cosineSpread,
  cosineText,
  IN_PROGRESS_SHOWN,
  NEIGHBOURS,
  nearestPassages,
  rankedBy,
  rankedNote,
  unitPassagesNote,
  type ChunkStats,
  type CosinePair,
  type CosineSpread,
  examplesHeading,
  examplesPointer,
  goldRankNote,
  goldUnitsSentence,
  honestExamples,
  nonGoldKept,
  scoreText,
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
// cảnh tắt, lọc và MMR tắt, top-N = 20, top-K = 10). PR 2b: khối Chunking riêng + công tắc câu ngữ cảnh.

// Thy chọn D2 (2026-11-26): MỘT lựa chọn cách chia (và công tắc câu ngữ cảnh) chung cho khối Chunking và khối kết quả —
// hai lựa chọn riêng dễ khiến người xem đọc đoạn của cách A nhưng kết quả tìm là cách B. Cả 2 khối hiện cùng bộ nút
// (`ChunkingControls`) trỏ vào cùng một state.
type Settings = { question: number; way: Way; context: boolean; retriever: Retriever; rerank: Rerank };

// Mặc định khi mở trang (ADR-0041): câu 1, recursive 500, câu ngữ cảnh tắt, hybrid RRF, chưa rerank
const START: Settings = {
  question: 1,
  way: DEFAULT_PIPELINE.way,
  context: DEFAULT_PIPELINE.context,
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

  // Index BM25 dựng lại khi đổi cách chia hoặc công tắc câu ngữ cảnh (thống kê của cả kho; ở "không chia" công tắc
  // không có hiệu lực — `buildWayIndex` tự coi là tắt)
  const index = useMemo(
    () => (demo ? buildWayIndex(demo, settings.way, settings.context) : null),
    [demo, settings.way, settings.context],
  );
  const question = demo?.questions.find((q) => q.number === settings.question) ?? null;
  const result = useMemo(() => {
    if (!demo || !index || !question) return null;
    const config = {
      ...DEFAULT_PIPELINE,
      way: settings.way,
      context: settings.context,
      retriever: settings.retriever,
      rerank: settings.rerank,
    };
    return runPipeline(demo, index, { question }, config);
  }, [demo, index, question, settings.way, settings.context, settings.retriever, settings.rerank]);

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
      <ChunkingBlock demo={demo} settings={settings} update={update} />
      <EmbeddingBlock demo={demo} way={settings.way} />
      <QuestionBlock demo={demo} question={question} onPick={(n) => update({ question: n })} />
      <PassagesBlock demo={demo} question={question} settings={settings} result={result} gold={gold} update={update} />
      <AboutBlock demo={demo} />
      <TermsBlock demo={demo} />
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
      {/* reviewer 2026-11-12: khung ANSWER từng chứa chính câu hỏi — nay trả lời "câu này kiểm điều gì" */}
      <AnswerRow
        answer={`Q${question.number} tests ${QUESTION_TESTS[question.number]}.`}
        points={[
          `**The question in English** (translation, for reading only): “${question.english}”`,
          `**Original wording** (${questionLanguage(question)}, the text every step searches with): “${question.text}”`,
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
  // "dense trần cần phần còn chờ" (câu ngữ cảnh bật + Dense): không có danh sách nào — khối không in số nào, kể cả 0
  // (0 đoạn đã xếp là kết quả thật của BM25, khác với "chưa tính")
  const inProgress = result.final === null;
  const bm25Only = result.retrieval.plan.status === "bm25-only";
  const ranker = rankedBy(settings.retriever, result.retrieval.plan.status);
  const ranked = result.final ?? [];
  const shown = result.cut ? ranked.slice(0, result.cut.shown) : [];
  const goldChunks = new Set(Object.values(question.gold_chunks[settings.way]).flat());
  const withContext = contextEffective(settings.way, settings.context);
  // Số dòng thật đang hiện: nhóm hoà vắt mốc K hiện cả nhóm (> K), danh sách ngắn hơn K (< K) — ux-reviewer vòng 1
  const shownNote =
    shown.length > K
      ? `The first ${K} (a design choice), plus ${shown.length - K} tied with the ${K}th.`
      : shown.length < K
        ? `Only ${shown.length} passages were ranked, fewer than the ${K} the page shows (a design choice).`
        : `The first ${K} of the ranked list (a design choice).`;
  // Hộp số chỉ hiện khi có danh sách (`inProgress` → không có hộp, xem AnswerRow bên dưới)
  const keyNumbers: KeyNumber[] = [
    {
      value: gold && gold.main.kind === "rank" ? rankText(gold.main.from, gold.main.to) : "—",
      label: "Correct answer rank",
      term: "answer-rank",
      note: goldRankNote(question, K),
    },
    {
      value: count(ranked.length),
      label: "Passages ranked",
      term: "passage",
      share: { part: ranked.length, whole: total, of: `${count(total)} passages` },
      note: rankedNote(ranker),
    },
    { value: count(shown.length), label: "Passages shown", term: "top-k", note: shownNote },
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
        <ChunkingControls
          demo={demo}
          settings={settings}
          update={update}
          shared={`The same settings as block ${ragNumber("chunking")}: changing them here changes them there.`}
        />
        <Control label="Retrieval (how passages are found)">
          <ToggleGroup
            label="Retrieval"
            options={(["bm25", "dense", "hybrid"] as const).map((key) => ({ key, label: RETRIEVERS_SHOWN[key] }))}
            value={settings.retriever}
            onChange={(retriever) => update({ retriever })}
          />
        </Control>
        <Control label={`Reranking (rescores the top ${TOP_N_DEFAULT} passages; ${TOP_N_DEFAULT} is a design choice)`}>
          <ToggleGroup
            label="Reranking"
            options={(["none", "cross_encoder", "haiku"] as const).map((key) => ({ key, label: RERANKS_SHOWN[key] }))}
            value={settings.rerank}
            onChange={(rerank) => update({ rerank })}
          />
        </Control>
      </div>
      <AnswerRow
        answer={inProgress ? IN_PROGRESS_SHOWN.dense : answerSentence(question, gold, K)}
        points={inProgress ? [] : unitPoints(question, gold)}
        // "in progress": không số nào có giá trị, không có danh sách → bỏ hộp số, chú giải và danh sách; câu trả lời
        // trải hết bề rộng (L5: không chừa cột phải toàn "—", không khung rỗng để lại khoảng trống)
        keyNumbers={inProgress ? undefined : keyNumbers}
        // Chú giải ở cột trái, cạnh hộp Key numbers: lấp khoảng trống ~330px dưới ANSWER ở 1440 (ux-reviewer 2026-11-12)
        extra={inProgress ? undefined : <PassagesNotes settings={settings} bm25Only={bm25Only} shown={shown} />}
        below={
          inProgress ? undefined : shown.length === 0 ? (
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
                  retriever={ranker}
                  rerank={settings.rerank}
                  isGold={goldChunks.has(row.chunk)}
                  withContext={withContext}
                />
              ))}
            </ol>
          )
        }
      />
      <MethodSection
        steps={[
          // Bước Chunking chuyển sang Method của khối Chunking (PR 2b)
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
            // 3 reviewer vòng 1 (2026-11-25): nhóm hoà vắt mốc N vào cả khối rerank (`rerankBlockSize`), mốc cắt K
            // không vượt khối → với K < N không đoạn "not reranked" nào hiện được
            plain: `Rereads the question and each of the top ${TOP_N_DEFAULT} passages (a design choice; passages tied with the ${TOP_N_DEFAULT}th are included) together with BAAI/bge-reranker-v2-m3 and sorts them by its score (a raw logit: higher means more relevant). Passages below them keep their order and are marked “not reranked”; since the page shows only the top ${K}, none of them appears here.`,
          },
          {
            title: "Claude Haiku reranking",
            plain: `Claude Haiku 5.5 (prompt version ${rerankPromptVersion(demo)}) gave each question–passage pair a score from 0 (not about the question’s topic) to 3 (answers the question directly); 2 or more is labelled “keep” (a design choice; on the prompt’s scale, 2 means “partly answers”). Equal scores keep the order of the step before, so two setups can rank the same passages differently.`,
          },
          {
            title: "Ranks and ties",
            plain:
              "Scores are rounded to 6 decimals. Passages with equal rounded scores are tied: they share a rank range, shown as “3–4”, because no single order between them is more correct. Claude Haiku reranking is the exception: equal Haiku scores keep the order of the step before, so they get separate ranks unless they were already tied there.",
          },
        ]}
        limits={[
          // ADR-0039 D2: rerank chấm chữ gốc của đoạn, không kèm câu ngữ cảnh, để số cặp không nhân đôi
          "Both rerankers score the original question and the passage alone, without its context sentence, so the number of scored pairs does not double.",
          "With the context sentence on, only BM25 uses it: dense similarity for passages with their context sentence is not computed yet, so Dense shows “in progress” and Hybrid falls back to BM25.",
          "The cross-encoder is run with a limit of 1,024 tokens per question–passage pair (a design choice; the model accepts more); every pair in this demo fits, so nothing is cut.",
          "With 19 content units, a different setup often moves the answer by only a few ranks; the page shows mechanisms, not which setup is best.",
        ]}
      />
    </Section>
  );
}

// Nhãn đứng trên nhóm nút: kiểu chữ chung `ControlLabel` (reviewer 2026-11-12: từng là TYPE.th, lệch /analytics)
function Control({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <ControlLabel>{label}</ControlLabel>
      {children}
    </div>
  );
}

function unitPoints(question: Question, gold: GoldAnswer | null): ReactNode[] {
  if (gold === null || question.gold_unit_ids.length < 2) return [];
  return question.gold_unit_ids.map(
    (unit, i) => `**Content unit ${i + 1} of the answer:** ${outcomeText(gold.units[unit], K)}.`,
  );
}

// Cột trái cạnh hộp Key numbers của khối kết quả: câu "in progress — showing BM25 only", câu về điểm Haiku, chú giải.
// Nhãn chỉ chú giải khi có dòng mang nó (reviewer 2026-11-12: "Not reranked" không bao giờ hiện vì K = 10 < N = 20,
// "tied across the cut" hiện mà không có chú giải)
function PassagesNotes({ settings, bm25Only, shown }: { settings: Settings; bm25Only: boolean; shown: Row[] }) {
  return (
    <div className="flex flex-col gap-4">
      {/* UI-0041-step-order cột E: "hybrid rơi về BM25" ghi "in progress — showing BM25 only" cạnh kết quả */}
      {bm25Only ? <p className={`m-0 ${TYPE.body}`}>{IN_PROGRESS_SHOWN.hybrid}</p> : null}
      {/* UI-0041-stable-rerank-ties cột E: câu ngắn cạnh kết quả rerank Haiku */}
      {settings.rerank === "haiku" ? (
        <p className={`m-0 ${TYPE.body}`}>
          Claude Haiku scores are whole numbers from 0 to 3, so many passages share a score. Equal Haiku scores keep the order
          of the retrieval step, so two setups with different retrieval can order the same Haiku scores differently.
        </p>
      ) : null}
      <PassageLegend
        rerank={settings.rerank}
        notReranked={settings.rerank !== "none" && shown.some((row) => row.notReranked)}
        acrossCut={shown.length > K}
        context={contextEffective(settings.way, settings.context)}
      />
    </div>
  );
}

function PassageLegend({
  rerank,
  notReranked,
  acrossCut,
  context,
}: {
  rerank: Rerank;
  notReranked: boolean;
  acrossCut: boolean;
  context: boolean;
}) {
  const items = [
    // copy-reviewer 2026-11-12: "covers" nói quá — đoạn chỉ cần chạm phần chứa ý
    { mark: <Mark>★</Mark>, name: "Correct answer", rule: "the passage belongs to the answer’s content unit (for Q5 and Q8, it must also overlap the part of the text that holds the answer)." },
    {
      mark: <Mark>=</Mark>,
      name: "Tied",
      rule:
        rerank === "haiku"
          ? "equal score after rounding; the rank is a range. Equal Haiku scores are tied only if they were already tied before reranking."
          : "equal score after rounding; the rank is a range.",
    },
  ];
  if (acrossCut) {
    items.push({ mark: <Mark>+</Mark>, name: "Tied across the cut", rule: `tied with the ${K}th passage, so it is shown even though it is past the first ${K}.` });
  }
  if (notReranked) {
    items.push({ mark: <Mark>·</Mark>, name: "Not reranked", rule: `outside the top ${TOP_N_DEFAULT}; it keeps its rank and score from retrieval.` });
  }
  if (rerank === "haiku") {
    items.push({ mark: <Mark>✓</Mark>, name: "Keep / drop", rule: "Haiku score 2 or more is “keep”, below 2 is “drop”; the label does not remove the passage." });
  }
  if (context) {
    items.push({
      mark: <Mark>¶</Mark>,
      name: "Context sentence",
      rule: "shown above a passage when BM25 searched it together with the passage; a passage that is a whole content unit has none.",
    });
  }
  // `[emoji]` / `[French flag]` hiện trong chữ đoạn → chú giải tại chỗ (reviewer 2026-11-12)
  items.push({
    mark: <Mark>[ ]</Mark>,
    name: "[emoji], [French flag]",
    rule: "placeholders in the text: an emoji that exists only on Threads, and a flag that some systems show as two letters.",
  });
  return <Legend items={items} />;
}

function Mark({ children }: { children: ReactNode }) {
  return (
    // whitespace-nowrap: ký hiệu "[ ]" rộng hơn cột 20px của Legend, từng ngắt thành 2 dòng (ux-reviewer vòng 1)
    <span aria-hidden="true" className="whitespace-nowrap font-mono text-[12.5px] font-semibold text-amber-700">
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
  withContext,
}: {
  demo: DemoFile;
  way: Way;
  row: Row;
  position: number;
  retriever: Retriever;
  rerank: Rerank;
  isGold: boolean;
  withContext: boolean;
}) {
  const chunk = demo.ways[way][row.chunk];
  const passage = demo.passages[chunk.passage];
  const unit = demo.units.find((u) => u.id === chunk.unit)!;
  const tied = row.tiedFrom < row.tiedTo;
  const labels = [
    isGold ? "★ correct answer" : null,
    tied ? "= tied" : null,
    position > K ? "+ tied across the cut" : null,
    row.notReranked && rerank !== "none" ? "· not reranked" : null,
    rerank === "haiku" && !row.notReranked ? (haikuKeeps(row.score) ? "✓ keep" : "✗ drop") : null,
  ].filter((label): label is string => label !== null);
  return (
    <li className="grid grid-cols-1 gap-3 border-t border-border-hairline py-5 first:border-t-0 sm:grid-cols-[96px_minmax(0,1fr)] sm:gap-6">
      {/* ux-reviewer vòng 1: ở 375 + Haiku, 4 mục trên 1 hàng bóp "rank 1" còn 30px, xuống dòng và đọc thành "rank 3" →
          hạng không bao giờ ngắt, các mục xuống hàng nguyên khối */}
      <div className="flex flex-row flex-wrap items-baseline gap-x-3 gap-y-1 sm:flex-col sm:gap-1">
        <span className={`${TYPE.mono} shrink-0 whitespace-nowrap font-semibold text-text-primary`}>
          rank {rankText(row.tiedFrom, row.tiedTo)}
        </span>
        <span className={`${TYPE.mono} text-text-secondary`}>{scoreText(row.score, rerank, row.notReranked)}</span>
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
        {withContext ? <ContextText demo={demo} passage={passage} /> : null}
        <PassageText demo={demo} passage={passage} unit={unit} />
      </div>
    </li>
  );
}

// Câu ngữ cảnh của một đoạn (ADR-0037 D7, Anthropic "Contextual Retrieval" 2024): bản tiếng Anh trước, chữ gốc ngay
// dưới (luật song ngữ), ghi model + phiên bản prompt (UI-0037-static-precomputed). Đoạn trùng cả bài: không có câu nào
// → không hiện gì (chú giải "¶ Context sentence" nói điều này)
function ContextText({ demo, passage }: { demo: DemoFile; passage: Passage }) {
  if (passage.context === null) return null;
  return (
    // Viền XÁM (Thy chọn 2026-11-26, ux-reviewer: amber dành cho thứ bấm được + khung ANSWER)
    <span className="flex flex-col gap-0.5 border-l-2 border-text-muted pl-3">
      <span className={TYPE.label}>
        ¶ Context sentence, English (written by Claude Haiku 5.5, prompt version {promptVersion(demo, "context")})
      </span>
      <span className={`${TYPE.body} text-text-primary`}>{showEmoji(passage.context_en ?? "")}</span>
      <span className={TYPE.label}>Context sentence, original language (what BM25 searches)</span>
      <span className={`${TYPE.body} text-text-primary`}>{showEmoji(passage.context)}</span>
    </span>
  );
}

// Chữ một đoạn: bản dịch tiếng Anh trước (kèm model + phiên bản prompt), rồi chữ gốc có dòng "Topic … · original
// language" (UnitText) — một cách hiện cho khối Loading và danh sách xếp hạng. `withTopic` = false khi các đoạn cùng
// một content unit đứng liền nhau (khối Loading): topic ghi 1 lần ở đầu, không lặp ở mọi post (reviewer 2026-11-12)
function PassageText({
  demo,
  passage,
  unit,
  withTopic = true,
}: {
  demo: DemoFile;
  passage: Passage;
  unit: Unit;
  withTopic?: boolean;
}) {
  return (
    <>
      <span className="flex flex-col gap-0.5">
        {/* UI-0037-static-precomputed: mỗi kết quả LLM ghi tên model + phiên bản prompt */}
        <span className={TYPE.label}>
          English (machine translation by Claude Haiku 5.5, prompt version {promptVersion(demo, translationJob(passage))})
        </span>
        <span className={`${TYPE.body} text-text-primary`}>{showEmoji(passage.en)}</span>
      </span>
      {withTopic ? (
        <UnitText text={showEmoji(passage.text)} topic={unitTopic(unit)} />
      ) : (
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className={TYPE.label}>Original language</span>
          <span className={`${TYPE.body} text-text-primary`}>{showEmoji(passage.text)}</span>
        </span>
      )}
    </>
  );
}

function unitTopic(unit: Unit): string | null {
  return unit.topic.id === null ? null : unit.topic.label_en;
}

// Bản đồ pipeline (Thy chốt 2026-11-12, sau khi hỏi "đã so với chuẩn của thầy chưa?"): đủ các bước của repo mẫu theo
// đúng số + tên, mỗi bước ghi trạng thái trên trang bản đầu và khối chứa nó — người quen chuẩn dò được bước nào ở đâu
function PipelineMapBlock() {
  const counts = (status: StepStatus) => PIPELINE_STEPS.filter((step) => step.status === status).length;
  // số ít / số nhiều theo số đếm (code-reviewer: câu không được viết cứng theo số hôm nay)
  const verb = (n: number, one: string, many: string) => (n === 1 ? one : many);
  const stages = [
    // reviewer 2026-11-12: "run once" lệch với BM25 dựng lại trong trình duyệt mỗi khi đổi cách chia
    {
      key: "indexing",
      title: "Stage 1 — Indexing",
      note: "Prepares the content units so they can be searched, before any question is asked. Here most of it was done in advance; the BM25 word counts are rebuilt in your browser when you change the chunking.",
    },
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
                          {/* ux-reviewer 2026-11-12: tên bước là tiêu đề thật (h4 dưới h3 của giai đoạn) để trình đọc
                              màn hình nhảy theo bước */}
                          <H level={4} className={TYPE.h4}>
                            {step.name}
                            {step.optional ? <span className={`${TYPE.note} font-normal`}> · optional</span> : null}
                          </H>
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

type UnitRow = { number: number; unit: Unit; characters: number };

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
  const characters = lengths.reduce((sum, length) => sum + length, 0);
  const months = [...new Set(units.map((unit) => unit.month))].sort();
  const monthCounts = months.map((month) => `${units.filter((u) => u.month === month).length} from ${monthText(month)}`);
  const unit = units[Math.min(picked, units.length - 1)];
  const shownNumber = Math.min(picked, units.length - 1) + 1;
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
          "**Source:** the Threads API (Meta’s official interface) returns the author’s posts and replies; a scheduled job stores them in a SQLite database about every 4 hours, and this demo reads a frozen copy.",
          // ADR-0004 quyết định 1 (`src/processing/thread_reconstruction.py:49#reaches_root`): mọi mắt xích là post của tác
          // giả — code-reviewer + copy-reviewer: câu "lần ngược về post mở đầu" thiếu điều kiện này là luật lỏng cũ.
          // copy-reviewer 2026-11-12: "whose" từng gắn nhầm vào "the author"
          "**One thread, one content unit:** a follow-up post is one of the author’s replies whose chain of “replied to” links leads back to the opening post through the author’s own posts only. Comments from other people, and the author’s answers to them, are left out.",
          `**Frozen:** the channel’s ${FROZEN_UNITS} most recent content units on Nov 5, 2026, each locked by its id, length and a SHA-256 hash. The author later deleted one of them from Threads, so ${count(units.length)} remain; before each publish the text is checked against Threads again.`,
          `**Text only, in its original form:** images and videos are not read, and the text keeps its case and its Vietnamese diacritics. Emoji that exist only on Threads come back from the API as the character ${THREADS_EMOJI} (checked against the Threads app on one post), so the page shows them as **[emoji]**.`,
        ]}
        keyNumbers={[
          {
            value: count(units.length),
            label: "Content units",
            term: "content-unit",
            note: `${monthCounts.join(", ")} (month of the opening post, Paris time).`,
          },
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
          // PR 2b (thẻ Thy duyệt 2026-11-26): tổng ký tự = toàn bộ chữ mà bước Chunking cắt; K2 tối đa 4 số mỗi hộp
          {
            value: count(characters),
            label: "Characters in all",
            note: `The text of the ${count(units.length)} content units together, which chunking then cuts into passages.`,
          },
        ]}
        below={
          <div className="flex flex-col gap-2">
            <SubSection
              title={`All ${count(units.length)} content units`}
              note="#1 = newest; month of the opening post, Paris time. Characters count the posts joined with a space."
            >
              <DataTable
                label="Every content unit of the demo, as a table"
                columns={[
                  {
                    header: "Content unit",
                    width: "18%",
                    cell: (row: UnitRow) => (
                      <>
                        #{row.number}
                        {row.number === shownNumber ? <span className={`${TYPE.label} ml-2 font-medium`}>selected</span> : null}
                      </>
                    ),
                  },
                  { header: "Month", width: "16%", cell: (row: UnitRow) => monthText(row.unit.month) },
                  { header: "Posts", width: "12%", numeric: true, cell: (row: UnitRow) => count(row.unit.posts.length) },
                  { header: "Characters", width: "16%", numeric: true, cell: (row: UnitRow) => count(row.characters) },
                  { header: "Topic (English)", width: "38%", cell: (row: UnitRow) => topicName(row.unit) },
                ]}
                rows={units.map((u, i) => ({ number: i + 1, unit: u, characters: lengths[i] }))}
                rowKey={(row) => row.unit.id}
                isSelected={(row) => row.number === shownNumber}
                minWidth={560}
                compact
              />
            </SubSection>
            <SubSection
              title="One content unit, post by post"
              note="Pick a content unit to read its posts; its row is marked “selected” in the table above."
            >
              {/* Thứ tự nút = thứ tự đóng băng, bài mới trước (`src/rag_demo/corpus.py:29#FROZEN_UNITS`) — reviewer
                  2026-11-12: nhãn phải nói #1 là bài nào */}
              <Control label="Inspect one content unit (#1 = newest)">
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
                {count(characterCount(unit.text))} characters ·{" "}
                {unitTopic(unit) === null ? "Unclustered: fits none of the topics" : `Topic: ${unitTopic(unit)}`}
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
                    <PassageText demo={demo} passage={demo.passages[chunk.passage]} unit={unit} withTopic={false} />
                  </li>
                ))}
              </ol>
            </SubSection>
          </div>
        }
      />
      <MethodSection
        steps={[
          {
            title: "Collect",
            plain:
              "A scheduled job reads the author’s posts and replies from the Threads API and stores them in SQLite about every 4 hours, while the author’s laptop is on.",
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

// Bộ nút cách chia + công tắc câu ngữ cảnh — một component cho khối Chunking và khối kết quả, cùng một state (Thy D2).
// `shared` = một câu nói 2 khối dùng chung thiết lập (người xem đổi ở khối này thì khối kia đổi theo)
function ChunkingControls({
  demo,
  settings,
  update,
  shared,
}: {
  demo: DemoFile;
  settings: Settings;
  update: (patch: Partial<Settings>) => void;
  shared: string;
}) {
  const total = demo.ways[settings.way].length;
  return (
    <>
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
      {/* UI-0039-chunking-options cột E: công tắc tắt ở "không chia", kèm một câu vì sao */}
      <Control label="Context sentence (added to a passage before it is indexed)">
        {settings.way === "whole" ? (
          <p className={`m-0 ${TYPE.note}`}>{CONTEXT_SHOWN.whole}</p>
        ) : (
          <>
            <ToggleGroup
              label="Context sentence"
              options={[
                { key: "off", label: "Off" },
                { key: "on", label: "On" },
              ]}
              value={settings.context ? "on" : "off"}
              onChange={(key) => update({ context: key === "on" })}
            />
            <p className={`m-0 ${TYPE.note}`}>{settings.context ? CONTEXT_SHOWN.on : CONTEXT_SHOWN.off}</p>
          </>
        )}
      </Control>
      <p className={`m-0 ${TYPE.note}`}>{shared}</p>
    </>
  );
}

// Khối Chunking (PR 2b, thẻ Thy duyệt 2026-11-26): bước 2 của repo mẫu thành khối riêng — cỡ đoạn của cách đang chọn
// (Key numbers), bảng 7 cách cạnh nhau (Thy D3: bảng 7 dòng, không histogram), các đoạn của một content unit, công
// tắc câu ngữ cảnh. Mọi số đọc từ file demo đang chạy (`chunkStats`), không viết tay
function ChunkingBlock({
  demo,
  settings,
  update,
}: {
  demo: DemoFile;
  settings: Settings;
  update: (patch: Partial<Settings>) => void;
}) {
  const [picked, setPicked] = useState(0);
  const way = settings.way;
  const rows = WAYS.map((w) => ({ way: w, stats: chunkStats(demo, w) }));
  const stats = rows.find((row) => row.way === way)!.stats;
  const spread = stats.lengths;
  const withContext = contextEffective(way, settings.context);
  const units = demo.units;
  const unit = units[Math.min(picked, units.length - 1)];
  const chunks = demo.ways[way].filter((chunk) => chunk.unit === unit.id).sort((a, b) => a.start - b.start);
  const embedding = provenanceText(demo, (p) => p.embedding_model, "text-embedding-3-small");
  return (
    <Section
      id="chunking"
      n={ragNumber("chunking")}
      short={ragShort("chunking")}
      title="Cut the content units into passages"
      purpose="How each content unit is cut into the passages that retrieval scores, how long those passages are, and what a context sentence adds."
    >
      <div className="flex flex-col gap-5">
        <ChunkingControls
          demo={demo}
          settings={settings}
          update={update}
          shared={`These settings also set the ranking in block ${ragNumber("passages")}.`}
        />
      </div>
      <AnswerRow
        answer={chunkingAnswer(way, units.length, stats.count, spread?.median ?? null)}
        points={[
          `**How it cuts:** ${WAYS_SHOWN[way].sentence}`,
          spread === null
            ? null
            : `**Shortest and longest:** ${count(spread.min)} and ${count(spread.max)} characters; short passages are shown as they are.`,
          `**Context sentence:** ${
            way === "whole"
              ? "not available, because each passage is a whole content unit."
              : withContext
                ? `on. BM25 searches each passage together with it; ${count(stats.count - stats.withContext)} of the ${count(stats.count)} passages ${stats.count - stats.withContext === 1 ? "is a whole content unit and has" : "are a whole content unit and have"} none.`
                : // code-reviewer vòng 1: không hứa "câu trên mỗi đoạn" — đoạn trùng cả bài không có câu nào
                  "off. With it on, each passage below that is not a whole content unit shows its context sentence above it."
          }`,
        ]}
        keyNumbers={[
          { value: count(stats.count), label: "Passages", term: "passage", note: `From ${count(units.length)} content units.` },
          {
            value: spread === null ? "—" : count(Math.round(spread.median)),
            label: "Characters per passage (median)",
            note:
              spread === null
                ? "No passages."
                : `Middle half ${count(Math.round(spread.q1))}–${count(Math.round(spread.q3))} (IQR), n = ${count(stats.count)}. Characters are Unicode code points, as the chunker counts them.`,
          },
          {
            value: count(stats.withContext),
            label: "Passages with a context sentence",
            term: "context-sentence",
            share: { part: stats.withContext, whole: stats.count, of: `${count(stats.count)} passages` },
            note: "A passage that is already a whole content unit has none.",
          },
        ]}
        below={
          <div className="flex flex-col gap-2">
            <SubSection
              title={`All ${WAYS.length} methods side by side`}
              note={`Passage lengths in characters; the row of the method chosen above is marked “selected”. n = number of passages.`}
            >
              <ChunkingTable rows={rows} selected={way} />
            </SubSection>
            <SubSection
              title="The passages of one content unit"
              note={unitPassagesNote(
                way,
                withContext,
                chunks.filter((chunk) => demo.passages[chunk.passage].context !== null).length,
                chunks.length,
              )}
            >
              {/* Thứ tự nút như khối Loading: thứ tự đóng băng, bài mới trước (`src/rag_demo/corpus.py:29#FROZEN_UNITS`) */}
              <Control label="Content unit (#1 = newest)">
                <ToggleGroup
                  label="Content unit for chunking"
                  mono
                  options={units.map((_, i) => ({ key: String(i), label: `#${i + 1}` }))}
                  value={String(picked)}
                  onChange={(key) => setPicked(Number(key))}
                />
              </Control>
              <p className={`m-0 ${TYPE.note}`}>
                {monthText(unit.month)} · {count(characterCount(unit.text))} characters ·{" "}
                {chunks.length === 1 ? "1 passage" : `${count(chunks.length)} passages`} ·{" "}
                {unitTopic(unit) === null ? "Unclustered: fits none of the topics" : `Topic: ${unitTopic(unit)}`}
              </p>
              <ol className="m-0 flex list-none flex-col p-0">
                {chunks.map((chunk, i) => {
                  const passage = demo.passages[chunk.passage];
                  return (
                    <li key={chunk.id} className="flex flex-col gap-2 border-t border-border-hairline py-5 first:border-t-0">
                      <span className={`${TYPE.mono} font-semibold text-text-primary`}>
                        passage {i + 1} of {chunks.length} · {count(characterCount(passage.text))} characters ·{" "}
                        {partText(chunkParts(demo, way, chunk.id))}
                      </span>
                      {withContext ? <ContextText demo={demo} passage={passage} /> : null}
                      <PassageText demo={demo} passage={passage} unit={unit} withTopic={false} />
                    </li>
                  );
                })}
              </ol>
            </SubSection>
          </div>
        }
      />
      <MethodSection
        steps={[
          {
            title: "No chunking, one per post",
            plain:
              "No chunking keeps each content unit whole. One per post cuts at the post boundaries the Threads API records, so each passage is one post (a Threads post holds at most 500 characters).",
          },
          {
            title: "Fixed windows",
            plain:
              // 3 reviewer vòng 1: câu cũ tự mâu thuẫn ("at the window's edge if there is none" vẫn cắt giữa từ). Đo
              // 2026-11-26 trên file demo: 152 chỗ cắt bên trong bài (83 / 45 / 24), 0 chỗ không nằm ở dấu cách
              "A window of 300, 500 or 800 characters ends at the last space in its second half; only if that half had no space would it end at the window’s edge, inside a word, which never happens in these content units. The next window starts at the first word inside the last 40, 60 or 100 characters, so neighbouring passages share a few words. That overlap, about 12% of the window, is within the 10–15% the reference project suggests.",
          },
          {
            title: "Recursive 500",
            plain:
              "The text is split into paragraphs; a paragraph longer than 500 characters is split into sentences. Neighbouring pieces are then joined as long as the result stays within 500 characters.",
          },
          {
            title: "Semantic",
            plain: `Each sentence is turned into a vector with OpenAI ${embedding}, and each sentence is compared with the next one. A cut goes between two sentences whose similarity is below the 25th percentile of all neighbouring pairs in the ${count(units.length)} content units, or where the next sentence would take the passage past 800 characters. The percentile and the 800 are design choices, not tuned values.`,
            formula: [
              "cut between s_i and s_(i+1) if cos(s_i, s_(i+1)) < P_25 or end(s_(i+1)) − start(passage) > 800",
              "s_i: sentence i of a content unit · P_25: 25th percentile of cos over every neighbouring pair of sentences in every content unit · start, end: character positions in the content unit",
            ],
          },
          {
            title: "Context sentence",
            // ux-reviewer vòng 1 (lỗi chặn): đoạn trùng cả bài chỉ được dịch, không có câu ngữ cảnh
            // (`src/rag_demo/demo_file.py:266#_context_of`)
            plain: `Before the demo was published, Claude Haiku 5.5 read each content unit and each of its passages that is not the whole content unit, and wrote 1–2 sentences that place the passage in the content unit, in the language of the post (prompt version ${promptVersion(demo, "context")}), following Anthropic’s Contextual Retrieval (2024). A passage that is the whole content unit gets no context sentence. With the switch on, BM25 indexes the context sentence and the passage together.`,
          },
          {
            title: "Lengths",
            plain:
              "A length is the number of Unicode code points in the passage, the unit the chunker itself counts in. The median and the middle half (IQR) use linear interpolation on the sorted lengths, the same method as the rest of the dashboard.",
            formula: ["Q(p) = x_(⌊h⌋) + (h − ⌊h⌋) · (x_(⌊h⌋+1) − x_(⌊h⌋)), h = (n − 1) · p, positions from 0 · IQR = Q(0.75) − Q(0.25)"],
          },
        ]}
        limits={[
          "Lengths are in characters, not in model tokens.",
          "Fixed windows and Recursive 500 can leave a short last passage, and Semantic can leave very short ones; they are shown as they are.",
          "The rerankers never see the context sentence: they score the passage alone.",
          "Dense similarity for passages with their context sentence is not computed yet; it is planned for a later version.",
          "The context sentences were written once; another model or prompt would write different ones.",
        ]}
      />
    </Section>
  );
}

// Bảng của trang (bảng 7 cách chia, bảng 19 bài, bảng cặp cosine): một kiểu cho cả 3 (PR 2b commit 3, NIT review
// commit 1: header lệch cột vì `pr-2` bị `pr-4` đè, cột nhảy khi đổi dòng chọn, hàng có hover mà không bấm được, số
// màu secondary trong khi bảng khác dùng primary). `table-fixed` + `colgroup`: bề rộng cột cố định, chữ đậm ở dòng
// chọn không đẩy cột. Mọi ô cùng `px-3` → header thẳng cột với số. Cột số căn phải, tabular-nums (K6). Dòng chọn có
// chữ (cột đầu tự ghi "selected"), không chỉ màu nền. Màn hẹp: cuộn ngang trong khung riêng, chọn được bằng bàn phím
// (axe scrollable-region-focusable)
type Column<R> = { header: string; width: string; numeric?: boolean; cell: (row: R) => ReactNode };

function DataTable<R>({
  label,
  columns,
  rows,
  rowKey,
  isSelected,
  minWidth,
  compact = false,
}: {
  label: string;
  columns: readonly Column<R>[];
  rows: readonly R[];
  rowKey: (row: R) => string;
  isSelected?: (row: R) => boolean;
  minWidth: number;
  compact?: boolean;
}) {
  const pad = compact ? "px-3 py-1.5" : "px-3 py-3";
  return (
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={label}>
      <table className="w-full table-fixed border-collapse" style={{ minWidth }}>
        <colgroup>
          {columns.map((column) => (
            <col key={column.header} style={{ width: column.width }} />
          ))}
        </colgroup>
        <thead>
          <tr className="border-b border-border-hairline align-bottom">
            {columns.map((column) => (
              <th
                key={column.header}
                scope="col"
                className={`px-3 py-2.5 ${column.numeric ? "text-right" : "text-left"} ${TYPE.th}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const on = isSelected?.(row) ?? false;
            return (
              <tr
                key={rowKey(row)}
                aria-current={on ? "true" : undefined}
                className={`border-t border-border-hairline align-baseline ${on ? "bg-warm-surface" : ""}`}
              >
                {columns.map((column, i) => {
                  const kind = column.numeric
                    ? `text-right ${TYPE.mono} whitespace-nowrap`
                    : `text-left ${TYPE.cell}`;
                  const className = `${pad} ${kind} text-text-primary ${on ? "font-semibold" : "font-normal"}`;
                  return i === 0 ? (
                    <th key={column.header} scope="row" className={className}>
                      {column.cell(row)}
                    </th>
                  ) : (
                    <td key={column.header} className={className}>
                      {column.cell(row)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Bảng 7 cách chia (Thy D3)
function ChunkingTable({ rows, selected }: { rows: { way: Way; stats: ChunkStats }[]; selected: Way }) {
  const number = (value: number | undefined) => (value === undefined ? "—" : count(Math.round(value)));
  const columns: Column<{ way: Way; stats: ChunkStats }>[] = [
    {
      header: "Chunking method",
      width: "28%",
      cell: ({ way }) => (
        <>
          {WAYS_SHOWN[way].label}
          {way === selected ? <span className={`${TYPE.label} ml-2 font-medium`}>selected</span> : null}
        </>
      ),
    },
    { header: "Passages (n)", width: "13%", numeric: true, cell: ({ stats }) => count(stats.count) },
    { header: "Median", width: "12%", numeric: true, cell: ({ stats }) => number(stats.lengths?.median) },
    {
      header: "Middle half (IQR)",
      width: "19%",
      numeric: true,
      cell: ({ stats }) => (stats.lengths === null ? "—" : `${number(stats.lengths.q1)}–${number(stats.lengths.q3)}`),
    },
    { header: "Shortest", width: "14%", numeric: true, cell: ({ stats }) => number(stats.lengths?.min) },
    { header: "Longest", width: "14%", numeric: true, cell: ({ stats }) => number(stats.lengths?.max) },
  ];
  return (
    <DataTable
      label="Passage lengths of every chunking method"
      columns={columns}
      rows={rows}
      rowKey={(row) => row.way}
      isSelected={(row) => row.way === selected}
      minWidth={600}
    />
  );
}

// Màu ô heatmap cosine: cùng thang tuần tự amber với heatmap giờ đăng của /analytics (MIX_MIN–MIX_MAX), trải tuyến tính
// từ cosine thấp nhất tới cao nhất của các cặp đang vẽ
function heatBackground(value: number, lo: number, hi: number): string {
  const mix = hi <= lo ? (MIX_MIN + MIX_MAX) / 2 : MIX_MIN + ((value - lo) / (hi - lo)) * (MIX_MAX - MIX_MIN);
  return `color-mix(in oklab, var(--amber-700) ${mix.toFixed(1)}%, var(--amber-soft))`;
}

function topicName(unit: Unit): string {
  return unitTopic(unit) ?? "Unclustered";
}

// Khối Embedding (PR 2b, Thy chọn D1 2026-11-26): heatmap 19 × 19 cosine giữa các content unit (cách "whole": mỗi đoạn
// là cả bài, mã chunk = thứ tự bài — đo 2026-11-26) + top-5 láng giềng gần của 1 đoạn ở cách chia đang chọn (lưới đủ
// đoạn 102 × 102 ~3px / ô trên điện thoại). Không có thiết lập làm đổi xếp hạng → bước 3 của bản đồ vẫn "fixed"
function EmbeddingBlock({ demo, way }: { demo: DemoFile; way: Way }) {
  const [unitIndex, setUnitIndex] = useState(0);
  const [passageIndex, setPassageIndex] = useState(0);
  const [active, setActive] = useState<{ a: number; b: number } | null>(null);
  const units = demo.units;
  const whole = cosineSpread(demo, "whole");
  const embedding = provenanceText(demo, (p) => p.embedding_model, "text-embedding-3-small");
  const unit = units[Math.min(unitIndex, units.length - 1)];
  const chunks = demo.ways[way].filter((chunk) => chunk.unit === unit.id).sort((a, b) => a.start - b.start);
  const chosen = chunks[Math.min(passageIndex, chunks.length - 1)];
  const neighbours = chosen ? nearestPassages(demo, way, chosen.id, NEIGHBOURS) : [];
  const unitNumber = (id: string) => units.findIndex((u) => u.id === id) + 1;
  const pairText = (a: number, b: number) =>
    `#${a + 1} (${topicName(units[a])}) and #${b + 1} (${topicName(units[b])}): cosine ${cosineText(cosineOf(demo, "whole", a, b))}`;
  return (
    <Section
      id="embedding"
      n={ragNumber("embedding")}
      short={ragShort("embedding")}
      title="Turn passages into vectors"
      purpose={`How similar the content units and their passages are once each is turned into a vector: the similarity that dense retrieval in block ${ragNumber("passages")} ranks by.`}
    >
      <AnswerRow
        answer={
          whole === null
            ? "There are too few content units to compare."
            : `Between any two of the ${count(units.length)} content units, cosine similarity runs from ${cosineText(whole.low.value)} to ${cosineText(whole.high.value)}, with a median of ${cosineText(whole.median)}.`
        }
        points={[
          `**Embedding:** before the demo was published, OpenAI ${embedding} turned every passage into a vector, a list of numbers in which texts with a similar meaning point in a similar direction.`,
          "**Cosine similarity:** compares the directions of two vectors; 1 means the same direction. It is a relative measure, not a share of meaning in common, so read the cells against each other.",
          `**Where it is used:** dense retrieval ranks the passages by the cosine between the question and each passage (block ${ragNumber("passages")}).`,
        ]}
        keyNumbers={
          whole === null
            ? undefined
            : [
                {
                  value: cosineText(whole.median),
                  label: "Cosine between two content units (median)",
                  term: "embedding",
                  note: `Middle half ${cosineText(whole.q1)}–${cosineText(whole.q3)} (IQR), n = ${count(whole.pairs)} pairs.`,
                },
                {
                  value: cosineText(whole.high.value),
                  label: "Most similar pair",
                  note: `#${whole.high.a + 1} (${topicName(units[whole.high.a])}) and #${whole.high.b + 1} (${topicName(units[whole.high.b])}).`,
                },
                {
                  value: cosineText(whole.low.value),
                  label: "Least similar pair",
                  note: `#${whole.low.a + 1} (${topicName(units[whole.low.a])}) and #${whole.low.b + 1} (${topicName(units[whole.low.b])}).`,
                },
              ]
        }
        below={
          <div className="flex flex-col gap-2">
            {whole === null ? null : (
              <SubSection
                title={`Similarity between the ${count(units.length)} content units`}
                note="Each cell is the cosine between two whole content units; darker means more similar. Rows and columns are the content units, #1 = newest."
              >
                <CosineMap
                  demo={demo}
                  spread={whole}
                  active={active}
                  onActivate={setActive}
                  readout={active ? pairText(active.a, active.b) : "Point at a cell for the two content units and their cosine; the table below lists every pair."}
                />
              </SubSection>
            )}
            <SubSection
              title="The nearest passages to one passage"
              note={`Cut with ${WAYS_SHOWN[way].label} (block ${ragNumber("chunking")}): the ${NEIGHBOURS} passages with the highest cosine to the chosen one, from all content units (${NEIGHBOURS} is a design choice).`}
            >
              <Control label="Content unit (#1 = newest)">
                <ToggleGroup
                  label="Content unit for nearest passages"
                  mono
                  options={units.map((_, i) => ({ key: String(i), label: `#${i + 1}` }))}
                  value={String(unitIndex)}
                  onChange={(key) => {
                    setUnitIndex(Number(key));
                    setPassageIndex(0);
                  }}
                />
              </Control>
              {chunks.length > 1 ? (
                <Control label="Passage of that content unit">
                  <ToggleGroup
                    label="Passage for nearest passages"
                    mono
                    options={chunks.map((_, i) => ({ key: String(i), label: `P${i + 1}` }))}
                    value={String(Math.min(passageIndex, chunks.length - 1))}
                    onChange={(key) => setPassageIndex(Number(key))}
                  />
                </Control>
              ) : null}
              {chosen ? (
                <>
                  <div className="flex flex-col gap-2 rounded-xl border border-border-hairline bg-bg-sunken px-5 py-4">
                    <span className={`${TYPE.mono} font-semibold text-text-primary`}>
                      chosen passage · #{unitNumber(chosen.unit)} · passage {chunks.indexOf(chosen) + 1} of {chunks.length}
                    </span>
                    <PassageText demo={demo} passage={demo.passages[chosen.passage]} unit={unit} />
                  </div>
                  <ol className="m-0 flex list-none flex-col p-0">
                    {neighbours.map((neighbour, i) => {
                      const chunk = demo.ways[way][neighbour.chunk];
                      const owner = units.find((u) => u.id === chunk.unit)!;
                      return (
                        <li
                          key={neighbour.chunk}
                          className="grid grid-cols-1 gap-3 border-t border-border-hairline py-5 first:border-t-0 sm:grid-cols-[96px_minmax(0,1fr)] sm:gap-6"
                        >
                          <div className="flex flex-row flex-wrap items-baseline gap-x-3 gap-y-1 sm:flex-col sm:gap-1">
                            <span className={`${TYPE.mono} whitespace-nowrap font-semibold text-text-primary`}>
                              nearest {i + 1}
                            </span>
                            <span className={`${TYPE.mono} text-text-secondary`}>{cosineText(neighbour.cosine)}</span>
                            <span className={TYPE.label}>cosine similarity</span>
                          </div>
                          <div className="flex min-w-0 flex-col gap-2">
                            <span className={TYPE.label}>
                              #{unitNumber(chunk.unit)} · {chunk.unit === chosen.unit ? "same content unit" : "another content unit"}
                            </span>
                            <PassageText demo={demo} passage={demo.passages[chunk.passage]} unit={owner} />
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                </>
              ) : null}
            </SubSection>
          </div>
        }
      />
      <MethodSection
        steps={[
          {
            title: "Embedding",
            plain: `Every passage of every chunking method, and every question, was sent once to OpenAI ${embedding} through its API before the demo was published. The vectors themselves are not in the demo file; only the cosines computed from them are.`,
          },
          {
            title: "Cosine similarity",
            plain:
              "Each vector is first scaled to length 1, so the cosine of two vectors is their dot product. The file stores every cosine rounded to 6 decimals; the page shows 3.",
            formula: ["cos(a, b) = (a · b) ÷ (‖a‖ ‖b‖)", "a, b: the vectors of two passages · a · b: sum of the products of their coordinates · ‖a‖: length of a"],
          },
          {
            title: "Colours",
            plain:
              "The colour of a cell grows linearly from the lowest to the highest cosine among the pairs drawn, on the same amber scale as the posting-time heatmap of the Analytics page. The diagonal (a content unit with itself) is not stored and stays grey.",
          },
          {
            title: "Nearest passages",
            // code-reviewer + copy-reviewer vòng 1 (lỗi chặn): hoà theo mã chunk của cách chia (`nearestPassages`), không
            // theo mảng `passages` của file (đã gộp chữ trùng, thứ tự khác ở 6/7 cách chia). Mã chunk dựng theo bài
            // (bài mới trước) rồi vị trí trong bài (`src/rag_demo/chunking.py#build_chunks`)
            plain: `For the chosen passage, every other passage of the same chunking method is sorted by its cosine to it, highest first; the first ${NEIGHBOURS} are shown. Equal cosines keep that chunking method’s order of passages: newest content unit first, then position in the text.`,
          },
        ]}
        limits={[
          "The vectors are of the original text, without the context sentence.",
          `The map compares whole content units only. A passage-by-passage map would need up to ${count(Math.max(...WAYS.map((w) => demo.ways[w].length)) ** 2)} cells, about 3 pixels each on a phone (a design choice); the nearest-passage list shows passages instead.`,
          `${count(units.length)} content units are too few to read groups of topics from the map.`,
        ]}
      />
    </Section>
  );
}

// Lưới 19 × 19 (D1). Ô không nhận focus (361 điểm dừng Tab quá nhiều cho bàn phím): lưới là `role="img"` có nhãn tóm
// tắt; người dùng bàn phím / trình đọc màn hình mở "Show as table" — mọi cặp, cosine cao nhất trước (Thy chọn
// 2026-11-27, như heatmap giờ đăng của /analytics). Ở màn hẹp lưới cuộn ngang trong khung riêng (như bảng), không bóp ô
// dưới cỡ đọc được
function CosineMap({
  demo,
  spread,
  active,
  onActivate,
  readout,
}: {
  demo: DemoFile;
  spread: CosineSpread;
  active: { a: number; b: number } | null;
  onActivate: (pair: { a: number; b: number } | null) => void;
  readout: string;
}) {
  const n = demo.ways.whole.length;
  const lo = spread.low.value;
  const hi = spread.high.value;
  const columns = { gridTemplateColumns: `32px repeat(${n}, minmax(0, 1fr))` };
  const units = demo.units;
  const pairs = cosinePairs(demo, "whole");
  const unitCell = (i: number) => `#${i + 1} · ${topicName(units[i])}`;
  return (
    <div className="flex flex-col gap-4">
      {/* ≥ xl: chú giải + dòng đọc cặp đứng cạnh lưới (lưới giới hạn 760px — không để ~400px trống bên phải, L5). Từ
          xl, không lg: ở 1024px cột phải chỉ còn ~120px (Thy chọn 2026-11-27). Dưới xl lưới cũng tối đa 760px (Thy chọn
          2026-11-27, ux-reviewer: ở 1024–1279px lưới 910px cao ~900px, dòng đọc cặp ngay dưới rơi khỏi màn hình) */}
      <div className="flex flex-col gap-3 xl:grid xl:grid-cols-[minmax(0,760px)_minmax(0,1fr)] xl:items-start xl:gap-8">
        <div className="w-full max-w-[760px] overflow-x-auto" tabIndex={0} role="region" aria-label="Cosine similarity map, scrolls sideways on small screens">
          <div
            role="img"
            aria-label={`Cosine similarity between every pair of the ${n} content units, from ${cosineText(lo)} to ${cosineText(hi)}; median ${cosineText(spread.median)}.`}
            // ở 1440 lưới trải hết card thì ô ~55px, cả lưới cao ~1.100px — cột 760px cho ô ~37px, vẫn đọc rõ
            className="grid min-w-[520px] gap-[2px]"
            style={columns}
            onMouseLeave={() => onActivate(null)}
          >
            <span aria-hidden="true" />
            {Array.from({ length: n }, (_, b) => (
              <span key={`c${b}`} aria-hidden="true" className={`${TYPE.mono} text-center text-text-secondary`}>
                {b + 1}
              </span>
            ))}
            {Array.from({ length: n }, (_, a) => (
              <Fragment key={`r${a}`}>
                <span aria-hidden="true" className={`${TYPE.mono} pr-1 text-right text-text-secondary`}>
                  #{a + 1}
                </span>
                {Array.from({ length: n }, (_, b) => {
                  const on = active !== null && ((active.a === a && active.b === b) || (active.a === b && active.b === a));
                  return (
                    <span
                      key={`${a}-${b}`}
                      aria-hidden="true"
                      onMouseEnter={() => onActivate(a === b ? null : { a: Math.min(a, b), b: Math.max(a, b) })}
                      className={`aspect-square rounded-[3px] border ${on ? "border-text-primary" : "border-border-hairline"}`}
                      style={{ background: a === b ? "var(--bg-sunken)" : heatBackground(cosineOf(demo, "whole", a, b), lo, hi) }}
                    />
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-3 xl:sticky xl:top-6">
          <p className={`m-0 min-h-[20px] ${TYPE.note} text-text-primary`} aria-live="polite">
            {readout}
          </p>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[12px] text-text-secondary">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-mono tabular-nums">{cosineText(lo)}</span>
              <span
                aria-hidden="true"
                className="h-2.5 w-28 rounded-full border border-border-hairline"
                style={{ background: `linear-gradient(90deg, ${heatBackground(lo, lo, hi)}, ${heatBackground(hi, lo, hi)})` }}
              />
              <span className="font-mono tabular-nums">{cosineText(hi)}</span>
              <span>cosine similarity</span>
            </div>
            <div className="flex items-center gap-2">
              <span aria-hidden="true" className="h-3 w-5 rounded-[3px] border border-border-hairline bg-bg-sunken" />
              <span>a content unit with itself (not stored)</span>
            </div>
          </div>
        </div>
      </div>
      {/* Nút mở bảng: cùng kiểu nút "Show as table" của /analytics (`PostingTimeHeatmap.tsx`) — viền + nền + chevron,
          vùng chạm 44px (C3) */}
      <details className="group">
        <summary className="inline-flex min-h-[44px] cursor-pointer list-none items-center gap-2 rounded-full border border-border-hairline bg-bg-surface px-4 text-[13px] font-semibold text-text-primary hover:border-amber-600 hover:text-amber-700 [&::-webkit-details-marker]:hidden">
          <CaretDown size={16} aria-hidden="true" className="transition-transform duration-150 group-open:rotate-180" />
          Show as table
        </summary>
        <div className="mt-3 flex flex-col gap-2">
          <p className={`m-0 ${TYPE.note}`}>
            All {count(pairs.length)} pairs of content units, the most similar first.
          </p>
          <DataTable
            label="Cosine similarity of every pair of content units, as a table"
            columns={[
              { header: "Content unit", width: "40%", cell: (pair: CosinePair) => unitCell(pair.a) },
              { header: "Other content unit", width: "40%", cell: (pair: CosinePair) => unitCell(pair.b) },
              { header: "Cosine", width: "20%", numeric: true, cell: (pair: CosinePair) => cosineText(pair.value) },
            ]}
            rows={pairs}
            rowKey={(pair) => `${pair.a}-${pair.b}`}
            minWidth={480}
            compact
          />
        </div>
      </details>
    </div>
  );
}

function AboutBlock({ demo }: { demo: DemoFile }) {
  const partly = nonGoldKept(demo, LLM_MAX_SCORE);
  // Mẫu số = cặp NGOÀI đáp án (copy-reviewer 2026-11-12; đo 2026-11-25: 4.012 trong 4.280 cặp)
  const pairs = `the ${count(partly.allPairs)} pairs of ${count(demo.questions.length)} questions × ${count(demo.passages.length)} distinct passages from all ${WAYS.length} chunking methods, minus the pairs in the fixed answers`;
  const examples = honestExamples(demo);
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
          `**The correct answers stay as fixed in advance.** Of the ${count(partly.pairs)} question–passage pairs outside the fixed answers, Claude Haiku rated ${count(partly.total - partly.top)} of them 2 (“partly answers”) and ${partly.top === 0 ? "none" : count(partly.top)} ${LLM_MAX_SCORE} (“answers directly”). Some do answer in part, others are Haiku mistakes${examplesPointer(examples.length)}. These ${count(partly.total)} pairs are still not marked as ★ correct answer.`,
          // copy-reviewer 2026-11-12: bản dịch còn giữ cả từ tiếng Pháp (logement, classe énergétique…); 2026-11-25:
          // chỉ tên hãng Việt giữ tiếng Việt (Gant, Tommy thì không) — "Thiên Long" còn trong bản dịch của 7 đoạn (đo
          // 2026-11-25), UI-0040-honest-data-notes bắt buộc nêu tên hãng
          "**English text is machine translation.** Dish names and Vietnamese brand names (such as Thiên Long pens) stay in Vietnamese, and French words the author used (such as logement or déstockage) often stay in French. A passage that starts mid-sentence sometimes keeps a few Vietnamese words.",
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
            term: "extra-partly",
            // nhãn ngắn: ở 375 chữ dài tràn mép hộp 18px (ux-shots L2, 2026-11-25); nghĩa đủ ở `note` ngay dưới
            share: { part: partly.total, whole: partly.pairs, of: `${count(partly.pairs)} other pairs` },
            note: `Question–passage pairs outside the fixed answers that Claude Haiku rated 2 or more. The ${count(partly.pairs)} are ${pairs}.`,
          },
        ]}
        below={
          examples.length > 0 ? (
            // UI-0040-honest-data-notes: ví dụ thật cho số trên (reviewer 2026-11-12), đọc chữ từ file đang chạy
            <SubSection title={examplesHeading(examples.length, partly.total)} note="Real pairs from the demo file, in the English translation.">
              <ol className="m-0 flex list-none flex-col p-0">
                {examples.map((example) => {
                  const q = demo.questions.find((item) => item.number === example.question)!;
                  const passage = demo.passages[example.passage];
                  return (
                    <li
                      key={`${example.question}-${example.passage}`}
                      className="flex flex-col gap-2 border-t border-border-hairline py-5 first:border-t-0"
                    >
                      <span className={`${TYPE.mono} font-semibold text-text-primary`}>
                        {example.kind} · Q{q.number} · Haiku score {scoreText(q.llm[example.passage].score, "haiku", false)}
                      </span>
                      <p className={`m-0 ${TYPE.body}`}>
                        <span className="font-semibold text-text-primary">Question:</span> “{q.english}”
                      </p>
                      <p className={`m-0 ${TYPE.body}`}>
                        <span className="font-semibold text-text-primary">Passage:</span> “{showEmoji(passage.en)}”
                      </p>
                      <p className={`m-0 ${TYPE.body}`}>
                        <span className="font-semibold text-text-primary">Why:</span> {example.why}
                      </p>
                    </li>
                  );
                })}
              </ol>
            </SubSection>
          ) : null
        }
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
            // PR 2b: câu ngữ cảnh nay là vai thứ 3 (công tắc ở khối Chunking); câu hỏi biến đổi vẫn chưa dùng (PR 3)
            plain: `On this page, Claude Haiku 5.5 plays three roles: translating every passage for reading (${translationVersions(demo)}), writing the context sentence of every passage that is not a whole content unit (prompt version ${promptVersion(demo, "context")}; block ${ragNumber("chunking")}), and scoring every question–passage pair from 0 to 3 (prompt version ${rerankPromptVersion(demo)}). The demo file also holds question rewrites it wrote for a later version of this page; they are not shown or used here. It never writes the final answer: the page only ranks passages from the channel.`,
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

// Bảng thuật ngữ của trang (luật dashboard: thuật ngữ định nghĩa tại chỗ hoặc ở bảng thuật ngữ; PR 2a, Thy chốt
// 2026-11-25). Cùng markup với /topics (`TermGroups`); nhãn Key numbers link tới đây bằng `term`. Hằng số đọc từ
// engine / file demo, không gõ số tay. Chữ là bản nháp: copy-reviewer đọc, Thy duyệt.
function TermsBlock({ demo }: { demo: DemoFile }) {
  const keep = demo.provenance.llm_keep_min_score;
  const groups: TermGroup[] = [
    {
      title: "1 · The data",
      lead: "What the demo searches, and what one search result is.",
      entries: [
        {
          id: "rag",
          term: "RAG",
          plain:
            "Retrieval-augmented generation: a system first retrieves passages relevant to a question, then a language model writes an answer from them. This page shows only the retrieval part; it ranks passages and writes no answer.",
        },
        {
          id: "content-unit",
          term: "Content unit",
          // copy-reviewer vòng 1: trang này đếm "posts" trong một content unit → "One post" tự mâu thuẫn; /topics giữ
          // câu của nó (gọi phần sau là "follow-up parts")
          plain: `One thread as the author published it: the opening post plus the follow-up posts the author added in the same thread. Replies to followers are left out. This demo searches ${count(demo.units.length)} frozen content units.`,
        },
        {
          id: "passage",
          term: "Passage",
          plain:
            "A piece of a content unit that retrieval scores and ranks. The chunking method decides how a content unit is cut into passages; with “No chunking”, a passage is the whole content unit.",
        },
        {
          id: "chunking",
          term: "Chunking",
          plain: `Cutting each content unit into passages. The page offers ${WAYS.length} methods; the method changes how many passages there are and how long they are. Block ${ragNumber("chunking")} compares them.`,
        },
        {
          id: "context-sentence",
          term: "Context sentence",
          plain:
            "One or two sentences, written in advance by Claude Haiku, that say where a passage sits in its content unit (Anthropic’s Contextual Retrieval). With the switch on, BM25 searches the sentence and the passage together. A passage that is already a whole content unit has none.",
        },
        {
          id: "precomputed",
          term: "Precomputed",
          plain:
            "Model scores (dense similarity, cross-encoder, Claude Haiku) computed once in advance and stored in the demo file. Your browser ranks and sorts them; it never calls a model.",
        },
      ],
    },
    {
      title: "2 · Finding passages",
      lead: "How retrieval scores each passage against the question.",
      entries: [
        {
          id: "bm25",
          term: "BM25",
          plain: `A keyword score: a passage scores higher the more of the question’s words it contains (each repeat adds less); rare words weigh more, and long passages are scored down. A passage that shares no word with the question scores 0 and is not ranked. Formula: block ${ragNumber("passages")}, Method.`,
        },
        // PR 2b commit 3 (NIT copy-reviewer): mục cũ "Embedding, dense similarity" chỉ định nghĩa cosine câu hỏi–đoạn,
        // trong khi khối Embedding so đoạn với đoạn → 2 mục: thước đo chung, rồi cách dense retrieval dùng nó
        {
          id: "embedding",
          term: "Embedding, cosine similarity",
          plain: `An embedding turns a text into a vector (a list of numbers) so that texts with similar meaning get vectors pointing in similar directions. Cosine similarity compares the directions of two vectors: 1 means the same direction, and higher means closer in meaning. Block ${ragNumber("embedding")} uses it to compare content units and passages with each other.`,
        },
        {
          id: "dense",
          term: "Dense similarity",
          plain:
            "The cosine similarity between the question’s vector and a passage’s vector. Dense retrieval ranks passages by it, so a passage close in meaning can rank high even with no word in common with the question.",
        },
        {
          id: "hybrid",
          term: "Hybrid (RRF)",
          plain: `Combines the BM25 list and the dense list by rank, not by score: each list gives a passage 1 ÷ (${RRF_K} + its rank), and the two values are added.`,
        },
        {
          id: "tie",
          term: "Tie, rank range",
          // 3 reviewer vòng 1: phải khớp ngoại lệ Haiku của Method khối 04 và chú giải "Tied" (`rerankHaiku`)
          plain:
            "Passages whose scores are equal after rounding to 6 decimals share a rank range such as “3–4”, because no order between them is more correct. The exception is Claude Haiku reranking: equal Haiku scores keep the order of the step before, so they share a range only if they were already tied there.",
        },
      ],
    },
    {
      title: "3 · Reranking",
      lead: "Rescoring the top of the list with a slower model that reads the question and the passage together.",
      entries: [
        {
          id: "top-n",
          term: "Top-N",
          // copy-reviewer vòng 2: khớp `rerankBlockSize` + Method khối 04 — nhóm hoà ở mốc N được rerank cả nhóm
          plain: `How many passages at the top of the retrieval list a reranker rescores: ${TOP_N_DEFAULT} (a design choice), plus any passages tied with the ${TOP_N_DEFAULT}th. Passages below them keep their order and are marked “not reranked”; with only the top ${K} shown, none appears on this page.`,
        },
        {
          id: "cross-encoder",
          term: "Cross-encoder",
          plain:
            "A model that reads the question and one passage together and returns one relevance score, a logit: any real number, higher means more relevant. Here: BAAI/bge-reranker-v2-m3.",
        },
        {
          id: "haiku-score",
          term: "Claude Haiku score",
          plain: `A score from 0 to 3 that Claude Haiku 5.5 gave each question–passage pair: 0 not about the question’s topic, 1 same topic but no help, 2 partly answers, 3 answers directly. ${keep} or more is labelled “keep” (a design choice); on this page the label never removes a passage.`,
        },
      ],
    },
    {
      title: "4 · Reading the result",
      lead: "What the marks and numbers next to the ranked passages mean.",
      entries: [
        {
          id: "correct-answer",
          term: "Correct answer (★)",
          plain:
            "The content units that answer a question, fixed by post id before any retrieval ran. A passage is marked ★ when it belongs to one of them; for Q5 and Q8 it must also overlap the part of the text that holds the answer.",
        },
        {
          id: "answer-rank",
          term: "Correct answer rank",
          plain: `The rank of the best-ranked correct passage in the full ranked list, before the top-${K} cut. When the answer needs 2 content units, it is the rank of the one found later.`,
        },
        {
          id: "top-k",
          term: "Top-K",
          plain: `How many passages the page shows: the first ${K} (a design choice). Passages tied with the ${K}th are shown too, marked “tied across the cut”.`,
        },
        {
          id: "extra-partly",
          term: "Extra “partly answers”",
          plain: `Question–passage pairs outside the fixed answers that Claude Haiku rated ${keep} or more. Some do answer in part, others are Haiku mistakes; the fixed answers are not changed.`,
        },
        {
          id: "placeholders",
          term: "[emoji], [French flag]",
          plain: `Placeholders in the text shown on this page. [emoji] stands for an emoji that exists only on Threads and comes back from the API as the character ${THREADS_EMOJI}; [French flag] stands for a flag that some systems show as two letters. The stored text and the scores keep the original characters.`,
        },
      ],
    },
  ];
  return (
    <Section
      id="terms"
      n={ragNumber("terms")}
      short={ragShort("terms")}
      title="Terms used on this page"
      purpose="Each term in plain words, in the order the page uses them; the formulas sit in the Method part of each block."
    >
      <TermGroups intro="Every term means exactly this everywhere on the page." groups={groups} />
    </Section>
  );
}
