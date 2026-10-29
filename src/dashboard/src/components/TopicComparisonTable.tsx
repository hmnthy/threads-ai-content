"use client";

import { AnswerRow, Bullets, Legend, MethodSection, Section, SubSection, TermLink, TYPE } from "@/components/AppBlock";
import { sectionShort } from "@/lib/topicSections";
import { VerdictLabel, VerdictMark, tooFewLabel } from "@/components/Verdict";
import type { ComparisonMetric, TopicComparisonRow } from "@/lib/api";
import {
  andList,
  count,
  familyBreakdown,
  formatP,
  pct,
  rawSignificantCount,
  signed,
  testTimes,
  testVerdict,
  type LandingData,
  type Noun,
} from "@/lib/landing";

// Bảng đủ họ Holm của trang /topics: ADR-0023 1c định nghĩa họ = mọi phép so có p xác định trên
// trang Topics (mọi topic × engagement / share rate / conversation) — panel engagement phía trên
// chỉ vẽ 1/3 họ, bảng này hiện đủ. Mọi số đọc từ `/topics/comparisons` (cùng lần kiểm định:
// median ở đây là số liệu lúc kiểm định, `snapshot_as_of`), không tính lại ở client.
// Nhãn kết quả: components/Verdict.tsx (Thy chốt 2026-10-29, ý b). Không làm mờ cả dòng (tương phản
// 2.3:1, ux-reviewer S11) — dòng ít bài dùng chữ muted + ◌ trong pill xám.
const QUESTION = "Does any topic differ from the rest of the channel in engagement, share or conversation rate?";
const METRICS: { id: ComparisonMetric; label: string; digits: number }[] = [
  { id: "engagement", label: "Engagement rate", digits: 2 },
  { id: "share_rate", label: "Share rate", digits: 3 },
  { id: "conversation", label: "Conversation rate", digits: 3 },
];

const TH = `px-2 py-2.5 ${TYPE.th}`;
const TD = `px-2 py-2 ${TYPE.mono}`;

const PURPOSE = "Runs the same test as block 03 on all three rates, so every comparison behind the answers on this page is visible, including the ones that did not pass.";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <Section id="all-tests" n="04" short={sectionShort("all-tests")} title={QUESTION} purpose={PURPOSE}>
      {children}
    </Section>
  );
}

export function TopicComparisonTable({ data, noun }: { data: LandingData; noun: Noun }) {
  const tests = data.topicTests;
  if (!tests) {
    // Hai lý do khác nhau, hai câu khác nhau (API lỗi ≠ chưa có lần kiểm định nào)
    return (
      <Shell>
        <p className={`m-0 ${TYPE.body}`}>
          {data.topicTestsStatus === "not-run"
            ? "The per-topic tests have not run on any clustering yet. They run in the daily NLP job after each clustering."
            : "The per-topic tests could not be loaded, so only the descriptions are shown. Reload in a moment."}
        </p>
      </Shell>
    );
  }
  const method = tests.method;
  if (tests.stale) {
    // UI-0023-stale-tests: các dòng thuộc lần gom cụm cũ — không hiện số của cách chia cũ dưới tên
    // topic hiện tại (kể cả cột mô tả); chỉ nói lý do và mốc giờ
    return (
      <Shell>
        <p className={`m-0 ${TYPE.body}`}>
          Hidden for now: the topics were re-drawn after the last tests ran
          {tests.computedAt ? ` (${testTimes(tests.computedAt, null)})` : ""}, so those results describe an older
          grouping of {noun.many}. They return once the tests are rerun on the current topics.
        </p>
      </Shell>
    );
  }
  const family = method.holm_family_size;
  const alpha = method.conclusion_alpha;
  const minPosts = method.min_posts_to_compare;
  const nameOf = new Map(data.topics.map((t) => [t.id, t.name]));
  const order = new Map(data.topics.map((t, i) => [t.id, i]));
  const rowsOf = (metric: ComparisonMetric, kind: TopicComparisonRow["kind"]) =>
    tests.rows
      .filter((row) => row.metric === metric && row.kind === kind)
      .sort((a, b) => (order.get(a.group_id) ?? 999) - (order.get(b.group_id) ?? 999));
  const topicRows = tests.rows.filter((row) => row.kind === "topic");
  const verdicts = topicRows.map((row) => testVerdict(row, method));
  const standing = topicRows.filter((_, i) => verdicts[i] === "higher" || verdicts[i] === "lower");
  // Mẫu số của câu trả lời: phép so trên topic đủ bài (có p Holm, không cờ mẫu nhỏ)
  const conclusive = topicRows.filter((row) => row.p_value_holm !== null && !row.insufficient_data).length;
  // Topic quá nhỏ vẫn có p Holm trong họ nhưng không bao giờ được nêu — nếu nó lọt dưới ngưỡng
  // thì câu trả lời phải nói ra, không được viết "none"
  const smallBelow = topicRows.filter(
    (row) => row.insufficient_data && row.p_value_holm !== null && row.p_value_holm < alpha,
  );
  const metricLabel = (metric: ComparisonMetric) =>
    METRICS.find((m) => m.id === metric)?.label.toLowerCase() ?? metric;
  const { below, expected } = rawSignificantCount(tests);
  const expectedText = Number.isInteger(expected) ? `${expected}` : expected.toFixed(1);
  const breakdown = familyBreakdown(tests, data.topics.length);

  // ADR-0024: chưa có luật bền → chỉ "For now …", không câu khẳng định
  const answer =
    conclusive === 0
      ? `Not yet: every topic has fewer than ${minPosts} ${noun.many} with recorded views, too few to conclude.`
      : standing.length === 0
        ? `For now, no: none of the ${conclusive} tests on topics large enough to conclude (of ${family} in all) has a corrected p below ${alpha}.`
        : `For now, ${standing.length} of the ${family} tests ${standing.length === 1 ? "stands" : "stand"} out after correction: ${andList(
            standing.map(
              (row) =>
                `${nameOf.get(row.group_id) ?? row.group_id} (${metricLabel(row.metric)}, ${
                  testVerdict(row, method) === "higher" ? "above" : "below"
                })`,
            ),
          )}.`;

  return (
    <Section id="all-tests" n="04" short={sectionShort("all-tests")} title={QUESTION} purpose={PURPOSE}>
      <AnswerRow
        answer={answer}
        points={[
          `Each row compares **one topic with the rest of the channel on one rate**: ${family} tests in all.`,
          "With this many tests, a few small p-values appear by chance alone, so every p is corrected for all of them (Holm).",
          "**Only the corrected p decides** a result.",
          smallBelow.length > 0
            ? `${andList(smallBelow.map((row) => `${nameOf.get(row.group_id) ?? row.group_id} (${metricLabel(row.metric)})`))} ${smallBelow.length === 1 ? "has" : "have"} a corrected p below ${alpha} but fewer than ${minPosts} ${noun.many} with recorded views, so ${smallBelow.length === 1 ? "it is" : "they are"} not concluded.`
            : null,
          standing.length > 0
            ? `A topic that stands out is a lead, not a finding: it holds for the current topics, which are re-clustered as new ${noun.many} arrive.`
            : null,
          tests.computedAt ? `Tests ran ${testTimes(tests.computedAt, tests.snapshotAsOf)}.` : null,
        ]}
        keyNumbers={[
          {
            value: `${family}`,
            label: "tests",
            note: breakdown ? `${breakdown}, every one with a p-value.` : "Every topic × rate with a p-value.",
            term: "holm",
          },
          {
            value: `${below}`,
            label: `with p < ${alpha} before correction`,
            // α × m là cận trên của số kỳ vọng (p hoán vị bảo thủ) — "at most about", không phải trần
            // của số đếm thật (lib/landing.ts rawSignificantCount)
            note: `If no topic truly differed, the expected number below ${alpha} by chance would be at most about ${expectedText} (${alpha} × ${family}). An expected count, not a test.`,
            term: "brunner-munzel",
          },
          {
            value: `${standing.length}`,
            label: `with corrected p < ${alpha}`,
            note: `Holm correction, on topics with at least ${minPosts} ${noun.many} with recorded views.`,
            term: "holm",
          },
        ]}
      />

      <SubSection
        title="How to read the result column"
        note={
          <>
            Every row of the three tables below gets exactly one of these labels (
            <TermLink term="result">full rule</TermLink>).
          </>
        }
      >
        <Legend
          items={[
            {
              mark: <VerdictMark verdict="higher" />,
              name: "Stood out above (▲) or below (▼)",
              rule: `corrected p below ${alpha}, and at least ${minPosts} ${noun.many} with recorded views on both sides. The arrow follows the sign of Cliff's δ.`,
            },
            {
              mark: <VerdictMark verdict="not distinguishable" />,
              name: "Not significant after correction",
              rule: `enough ${noun.many} on both sides (n ≥ ${minPosts}), but the corrected p is ${alpha} or more. The data cannot show a gap; that is not proof there is none.`,
            },
            {
              mark: <VerdictMark verdict="too few posts" />,
              name: tooFewLabel(noun, minPosts),
              rule: `the topic or the rest has fewer than ${minPosts} ${noun.many} with recorded views. Its p still counts in the correction, but it never stands out. Shown in grey.`,
            },
            ...(verdicts.includes("not tested")
              ? [
                  {
                    mark: <VerdictMark verdict="not tested" />,
                    name: "Not tested",
                    rule: `no p-value could be computed (for example, the topic has no ${noun.many} with recorded views).`,
                  },
                ]
              : []),
          ]}
        />
        <span className={`${TYPE.note} lg:hidden`}>
          On a narrow screen, scroll each table sideways; the topic column stays in place.
        </span>
      </SubSection>

      {METRICS.map((metric) => {
        const rows = rowsOf(metric.id, "topic");
        const noise = rowsOf(metric.id, "noise")[0];
        const channel = rowsOf(metric.id, "channel")[0];
        const rate = (value: number, n: number) => (n > 0 ? pct(value, metric.digits) : "—");
        const tested = rows.filter((row) => row.p_value_holm !== null).length;
        const comparable = rows.filter((row) => row.p_value_holm !== null && !row.insufficient_data).length;
        return (
          <div key={metric.id} className="flex flex-col gap-3 border-t border-border-hairline pt-7">
            <div className="flex flex-col gap-1">
              <h3 className={`m-0 ${TYPE.h3}`}>{metric.label}: each topic vs the rest</h3>
              <p className={`m-0 ${TYPE.note}`}>
                {tested} tests · {comparable} on topics large enough to conclude ·{" "}
                <TermLink term="rates">how the rate is computed</TermLink>
              </p>
            </div>
            {/* δ + CI và Holm p + p gộp thành ô 2 dòng để 8 cột vừa khung từ 1024px; < lg cuộn ngang với
                cột tên dính, hẹp 124px ở điện thoại (ux-reviewer C1/N7, phương án B) */}
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] table-fixed border-collapse text-left">
                <colgroup>
                  <col className="w-[124px] md:w-[22%]" />
                  <col className="w-[44px]" />
                  <col className="w-[72px]" />
                  <col className="w-[104px]" />
                  <col className="w-[150px]" />
                  <col className="w-[136px]" />
                  <col />
                  <col className="w-[84px]" />
                </colgroup>
                <thead>
                  <tr className="border-b border-rule align-bottom">
                    <th scope="col" className={`${TH} sticky left-0 z-[1] bg-bg-card`}>
                      Topic
                    </th>
                    <th scope="col" className={`${TH} text-right`}>
                      <TermLink term="median">n</TermLink>
                    </th>
                    <th scope="col" className={`${TH} text-right`}>
                      <TermLink term="median">Median</TermLink>
                    </th>
                    <th scope="col" className={`${TH} whitespace-nowrap text-right`}>
                      <TermLink term="rest">Rest: n · median</TermLink>
                    </th>
                    <th scope="col" className={`${TH} whitespace-nowrap text-right`}>
                      <TermLink term="cliffs-delta">Cliff&apos;s δ</TermLink>
                      <br />
                      <TermLink term="ci">95% CI, unadjusted</TermLink>
                    </th>
                    <th scope="col" className={`${TH} whitespace-nowrap text-right`}>
                      <TermLink term="holm">Holm p</TermLink>
                      <br />
                      <TermLink term="brunner-munzel">p before correction</TermLink>
                    </th>
                    <th scope="col" className={TH}>
                      <TermLink term="result">Result</TermLink>
                    </th>
                    <th scope="col" className={`${TH} whitespace-nowrap text-right`}>
                      <TermLink term="stood-out">Stood out in</TermLink>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const verdict = testVerdict(row, method);
                    const marked = verdict === "higher" || verdict === "lower";
                    const muted = verdict === "too few posts" || verdict === "not tested";
                    const tally = row.history;
                    const tone = marked ? "text-amber-700" : muted ? "text-text-muted" : "text-text-primary";
                    return (
                      <tr key={row.group_id} className="border-b border-bg-surface align-baseline hover:bg-bg-sunken">
                        <th
                          scope="row"
                          className={`sticky left-0 z-[1] bg-bg-card px-2 py-2 ${TYPE.cell} font-normal ${
                            marked ? "font-semibold text-amber-700" : muted ? "text-text-muted" : "text-text-primary"
                          }`}
                        >
                          {/* < lg: ký hiệu kết quả đi theo cột tên đang dính — thấy kết quả không cần cuộn (ux-reviewer S1) */}
                          <span className="mr-1 lg:hidden">
                            <VerdictMark verdict={verdict} />
                          </span>
                          {nameOf.get(row.group_id) ?? row.group_id}
                        </th>
                        <td className={`${TD} text-right ${tone}`}>{row.group.n}</td>
                        <td className={`${TD} text-right ${tone}`}>{rate(row.group.median, row.group.n)}</td>
                        <td className={`${TD} whitespace-nowrap text-right text-text-secondary`}>
                          {row.rest ? `${row.rest.n} · ${rate(row.rest.median, row.rest.n)}` : "—"}
                        </td>
                        <td className={`${TD} text-right`}>
                          <span className={`block ${tone}`}>
                            {row.effect_size === null ? "—" : signed(row.effect_size)}
                          </span>
                          <span className="block whitespace-nowrap text-text-muted">
                            {row.effect_size_ci_low === null || row.effect_size_ci_high === null
                              ? "no CI"
                              : `${signed(row.effect_size_ci_low)} to ${signed(row.effect_size_ci_high)}`}
                          </span>
                        </td>
                        <td className={`${TD} text-right`}>
                          <span className={`block ${tone}`}>
                            {row.p_value_holm === null ? "—" : formatP(row.p_value_holm)}
                          </span>
                          <span className="block text-text-muted">
                            {row.p_value === null ? "—" : formatP(row.p_value)}
                          </span>
                        </td>
                        <td className="px-2 py-2">
                          <VerdictLabel verdict={verdict} minPosts={minPosts} noun={noun} />
                        </td>
                        <td className={`${TD} whitespace-nowrap text-right text-text-secondary`}>
                          {tally && tally.clusterings > 0
                            ? `${tally.stood_out} of ${tally.clusterings}${
                                tally.direction ? (tally.direction === "higher" ? " ▲" : " ▼") : ""
                              }`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                  {noise ? (
                    <tr className="border-b border-dashed border-rule bg-bg-sunken align-baseline text-text-muted">
                      <th scope="row" className={`sticky left-0 z-[1] bg-bg-sunken px-2 py-2 ${TYPE.cell} font-normal`}>
                        Unclustered
                      </th>
                      <td className={`${TD} text-right`}>{noise.group.n}</td>
                      <td className={`${TD} text-right`}>{rate(noise.group.median, noise.group.n)}</td>
                      <td colSpan={5} className={`px-2 py-2 ${TYPE.cell}`}>
                        Described, not tested: unclustered is not a topic, and it stays in every topic&apos;s comparison
                        group.
                      </td>
                    </tr>
                  ) : null}
                  {channel ? (
                    <tr className="align-baseline text-text-secondary">
                      <th scope="row" className={`sticky left-0 z-[1] bg-bg-card px-2 py-2 ${TYPE.cell} font-semibold text-text-primary`}>
                        Whole channel
                      </th>
                      <td className={`${TD} text-right`}>{channel.group.n}</td>
                      <td className={`${TD} text-right text-text-primary`}>
                        {rate(channel.group.median, channel.group.n)}
                      </td>
                      <td colSpan={5} className={`px-2 py-2 ${TYPE.cell}`}>
                        Reference only: each topic is compared with the rest of the channel, not with this median.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}

      <SubSection title="Notes on the tables">
      <Bullets
        items={[
          "Medians here come from the data the tests ran on, so they can differ slightly from the live medians in the engagement block above.",
          `The 95% CI of δ is **not corrected** for the ${family} tests, so it can exclude 0 while the corrected p stays at ${alpha} or more. Only the corrected p decides.`,
          `**“Stood out in k of m”**: of the m clusterings in which the topic had enough ${noun.many} to test, the k in which it stood out (▲ above, ▼ below). A record across re-clusterings, not today's result.`,
          `A dash (—) in that column means the topic has never had enough ${noun.many} to test.`,
        ]}
      />
      </SubSection>

      <MethodSection
        steps={[
          {
            title: "Two groups",
            plain: `For each topic and each rate: the topic's ${noun.many} against every other ${noun.one} in the same clustering run, unclustered ones included. Only ${noun.many} with recorded views count.`,
          },
          {
            title: "Effect size",
            plain: `Cliff's δ: the chance a random ${noun.one} from the topic has the higher rate, minus the chance it has the lower one.`,
            formula: "δ = ( #{x > y} − #{x < y} ) ÷ (n_topic · n_rest)",
          },
          {
            title: "Test",
            plain: `Two-sided Brunner-Munzel test, with its p worked out from B = ${count(method.n_permutations)} random reshuffles of which ${noun.many} belong to the topic (seed ${method.random_seed}). It assumes neither bell-shaped data nor equal spread.`,
            formula: ["T = (π̂ − 1/2) ÷ SE,   π̂ = (1 − δ̂) ÷ 2", "k_{+} = #{T* ≥ T},   k_{−} = #{T* ≤ T}", "p = min(1, 2 · min(k_{+} + 1, k_{−} + 1) ÷ (B + 1))"],
          },
          {
            title: "Confidence interval",
            plain: "95% CI of δ from the same reshuffles (inverting the test), not corrected for the number of tests.",
            formula: ["low  = δ̂ + 2 · q_{0.025} · SE", "high = δ̂ + 2 · q_{0.975} · SE"],
          },
          {
            title: "Correction",
            plain: `Holm's method across all ${family} tests${breakdown ? ` (${breakdown})` : ""}, small topics included: the chance of even one false alarm stays at ${Math.round(alpha * 1000) / 10}% or less.`,
            formula: `Holm p_(i) = max over j ≤ i of min(1, (${family} − j + 1) · p_(j))`,
          },
          {
            title: "Decision",
            plain: `A topic stands out only if its corrected p is below ${alpha} and both the topic and the rest have at least ${minPosts} ${noun.many} with recorded views.`,
          },
        ]}
        limits={[
          `The three rates share one denominator (views), and every test reuses the same ${noun.many} in its comparison group, so the tests are not independent; Holm's correction does not need them to be.`,
          "p-values come from random reshuffles, so they carry a small simulation error; the seed is fixed so the page always shows the same numbers.",
          "A CI is missing when the two groups do not overlap at all (δ = ±1), when every value is equal, or when a group is too small for the test.",
          "Corrected p-values are capped at 1.",
          "The comparisons are **exploratory**: they depend on where the topic boundaries fall, and they change when the topics are re-drawn.",
          `A gap would be **an association, not an effect** of the topic: topics differ in when they were posted, and the channel's audience changed over time.`,
        ]}
        more={
          <>
            Every symbol is explained in{" "}
            <a href="#term-rest" className="font-medium text-amber-700 underline underline-offset-4">
              Comparing a topic with the rest of the channel
            </a>
            .
          </>
        }
      />
    </Section>
  );
}
