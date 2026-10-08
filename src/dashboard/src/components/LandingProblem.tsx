import { SECTION } from "@/components/LandingParts";
import { count, type LandingData } from "@/lib/landing";

// "Problem" — 3 câu hỏi của người làm kênh (handoff §3.2). Không sticky cột trái: gãy khi 1 cột.
export function LandingProblem({ data }: { data: LandingData | null }) {
  const posts = data && data.summary.content_units > 0 ? count(data.summary.content_units) : null;
  const answers =
    data && data.summary.reply_roles.author_answer > 0
      ? count(data.summary.reply_roles.author_answer)
      : null;
  const questions = [
    {
      id: "Q1",
      question: "Which posts did well for this channel, not in general?",
      shows: "Views, likes, replies, reposts and quotes, one post at a time.",
      missing:
        "A reference point: a 3% engagement rate means little until you know what is usual for this channel.",
    },
    {
      id: "Q2",
      question: "What does the channel write about, and which of it lands?",
      shows: "Posts in time order.",
      missing:
        "Topics found in the text itself, even though posts mix Vietnamese, French and English.",
    },
    {
      id: "Q3",
      question: "Has the channel already answered this somewhere?",
      shows: "Replies inside each post's own thread.",
      missing: "One place to search the posts and the answers to followers, by meaning as well as keywords.",
    },
  ];

  return (
    <section
      id="problem"
      data-screen-label="02 Problem"
      className={`${SECTION} grid grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] items-start gap-14 border-t border-rule py-[104px]`}
    >
      <div className="flex flex-col gap-5">
        <span className="font-mono text-[13px] font-medium text-amber-600">01 · Problem</span>
        <h2 className="m-0 text-[clamp(32px,3.6vw,46px)] font-extrabold leading-[1.08] tracking-[-0.035em] [text-wrap:balance]">
          {posts && answers
            ? `${posts} posts and ${answers} answers to followers. Threads can't say what they add up to.`
            : "Hundreds of posts and answers to followers. Threads can't say what they add up to."}
        </h2>
        <p className="m-0 text-base leading-[1.65] text-text-secondary [text-wrap:pretty]">
          @thydilammuon writes for Vietnamese students and workers in France: alternance, job
          hunting, everyday life. Running the channel raises three questions the Threads app has no
          screen for.
        </p>
      </div>
      <div className="flex flex-col">
        {questions.map((q, i) => (
          <div
            key={q.id}
            className={`flex flex-col gap-3.5 ${i === 0 ? "pb-8" : "border-t border-rule py-8"} ${
              i === questions.length - 1 ? "pb-0" : ""
            }`}
          >
            <span className="font-mono text-[13px] font-semibold text-text-muted">{q.id}</span>
            <span className="text-[26px] font-bold leading-[1.25] tracking-[-0.02em]">
              {q.question}
            </span>
            <div className="grid grid-cols-[112px_minmax(0,1fr)] gap-x-4 gap-y-2 text-[14.5px] leading-[1.55]">
              <span className="text-text-muted">Threads shows</span>
              <span className="text-text-secondary">{q.shows}</span>
              <span className="text-text-muted">Missing</span>
              <span className="text-text-primary">{q.missing}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
