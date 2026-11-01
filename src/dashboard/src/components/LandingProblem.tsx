import { TYPE } from "@/lib/typeScale";
import { LAYER_GRID, SECTION, SectionHead } from "@/components/LandingParts";
import { count, type LandingData } from "@/lib/landing";

// "Problem" — 3 câu hỏi của người làm kênh (handoff §3.2). Thy 2026-11-01 (ADR-0032): đầu section trải ngang, Q1–Q3
// thành 3 cột từ 1024px, cùng lưới với 3 tầng Measure / Group / Search của "Approach" ngay dưới (Q1 trên Measure…),
// mỗi câu hỏi là tiêu đề khối thật (h3 26px) — bỏ bố cục 2 cột để lại khoảng trống ~360px (L5)
export function LandingProblem({ data }: { data: LandingData | null }) {
  const units = data && data.summary.content_units > 0 ? count(data.summary.content_units) : null;
  const answers =
    data && data.summary.reply_roles.author_answer > 0
      ? count(data.summary.reply_roles.author_answer)
      : null;
  const questions = [
    {
      id: "Q1",
      question: "Which content units did well by this channel's own standard?",
      shows: "Views, likes, replies, reposts and quotes, one post at a time.",
      missing:
        "A reference point: a 3% engagement rate means little until you know what is usual for this channel.",
    },
    {
      id: "Q2",
      question: "What does the channel write about, and which of it lands?",
      shows: "Posts in time order.",
      missing: "Topics found in the text itself, even though the channel mixes Vietnamese, French and English.",
    },
    {
      id: "Q3",
      question: "Has the channel already answered this somewhere?",
      shows: "Replies inside each post's own thread.",
      missing:
        "One place to search the content units and the answers to followers, by meaning as well as keywords.",
    },
  ];

  return (
    <section
      id="problem"
      data-screen-label="02 Problem"
      className={`${SECTION} flex flex-col gap-12 border-t border-rule py-[104px]`}
    >
      <SectionHead
        eyebrow="01 · Problem"
        title={
          units && answers
            ? `${units} content units and ${answers} answers to followers. Threads can't say what they add up to.`
            : "Hundreds of content units and answers to followers. Threads can't say what they add up to."
        }
      >
        @thydilammuon writes for Vietnamese students and workers in France: alternance, job hunting, everyday life.
        Running the channel raises three questions the Threads app has no screen for.
      </SectionHead>
      <div className={`grid grid-cols-1 gap-y-10 ${LAYER_GRID}`}>
        {questions.map((q) => (
          <div key={q.id} className="flex flex-col gap-3.5 border-t-2 border-text-primary pt-5">
            <span className={`${TYPE.eyebrowNum} text-amber-600`}>{q.id}</span>
            <h3 className={`m-0 ${TYPE.h2} [text-wrap:balance]`}>{q.question}</h3>
            <dl className="m-0 grid grid-cols-[112px_minmax(0,1fr)] gap-x-4 gap-y-2">
              <dt className={`${TYPE.body} font-semibold text-text-muted`}>Threads shows</dt>
              <dd className={`m-0 ${TYPE.body}`}>{q.shows}</dd>
              <dt className={`${TYPE.body} font-semibold text-text-muted`}>Missing</dt>
              <dd className={`m-0 ${TYPE.body} text-text-primary`}>{q.missing}</dd>
            </dl>
          </div>
        ))}
      </div>
    </section>
  );
}
