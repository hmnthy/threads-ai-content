import type { ReactNode } from "react";
import { Formula, rich, Section, TYPE } from "@/components/AppBlock";
import { sectionShort } from "@/lib/topicSections";
import type { ClusterRun, ComparisonMethod } from "@/lib/api";
import { count } from "@/lib/landing";

// Phần "cách tính" của /topics — thay bảng thuật ngữ cũ (Thy 2026-10-29, ý 5: "thiếu theory recap,
// topic tính thế nào, công thức gì"). Mỗi mục: chữ thường → công thức → nghĩa từng ký hiệu → giá
// trị của lần chạy này. Công thức đối chiếu code (2026-10-29), không lấy từ sách:
// - embedding: bge-m3, normalize_embeddings=True (src/nlp/embeddings.py:34, :56), trên full_text
//   (src/pipeline/clustering_export.py:71-74)
// - UMAP n_components/n_neighbors/random_state (src/nlp/topics.py:45-48, :86-90); metric để mặc định
// - HDBSCAN min_cluster_size, leaf, euclidean trên toạ độ UMAP (src/nlp/topics.py:93-99)
// - tâm + độ tương đồng: trung bình vector chuẩn hoá rồi chuẩn hoá lại, tích vô hướng
//   (src/nlp/topic_profile.py:238-249)
// - c-TF-IDF W = tf · log(1 + A/f), nhiễu là 1 lớp nền, từ có trong ≥ 2 unit của topic, bỏ từ có ở
//   ≥ 80% topic khi có ≥ 3 topic, giữ 8 từ (src/nlp/topic_profile.py:40-49, :161-234)
// - DBCV = hdbscan.validity.validity_index trên toạ độ UMAP (src/pipeline/cluster_wsl.py:126-135)
// - ARI Hubert-Arabie (src/nlp/topic_profile.py:252-272), 2 biến thể (src/pipeline/clustering_import.py:169-195)
// - Brunner-Munzel hoán vị có chuẩn hoá, p 2 phía +1, CI đảo ngược phép kiểm (Pauly và cộng sự
//   2016), Cliff's δ, Holm step-down (src/analysis/significance.py:168-331)
// - IQR: statistics.quantiles(n=4, method="inclusive") (src/analysis/stats.py:62)
// Tham số thay đổi được đọc từ API (`run.params`, `method`); API chưa trả thì viết bằng chữ, không
// gõ số thay. Hằng số cố định của code (8 từ khoá, ≥ 2 unit, 80%, 15 unit đặt tên) ghi kèm file:line ở trên.

interface Entry {
  id: string; // anchor `term-<id>` — các khối trên trang link tới đây
  term: string;
  plain: ReactNode;
  formula?: string[];
  where?: ReactNode[];
  thisRun?: ReactNode;
}

// Ký hiệu có chỉ số (`w_ij`) → Formula vẽ <sub>; tên hàm/ID trong code (có "." hoặc "=") giữ nguyên
function Mono({ children }: { children: ReactNode }) {
  if (typeof children === "string" && /[_^]/.test(children) && !/[.=]/.test(children)) {
    return <Formula>{children}</Formula>;
  }
  return <code className="font-mono text-[12.5px] text-text-primary">{children}</code>;
}

function groups(run: ClusterRun | null, method: ComparisonMethod | null, minPosts: number): {
  title: string;
  lead: string;
  entries: Entry[];
}[] {
  const param = (key: string) => {
    const value = run?.params[key];
    return value === undefined || value === null ? null : String(value);
  };
  const dims = param("umap_n_components");
  const neighbours = param("umap_n_neighbors");
  const umapSeed = param("umap_random_state");
  const minCluster = param("hdbscan_min_cluster_size");
  const selection = param("cluster_selection_method");
  const alpha = method ? String(method.conclusion_alpha) : "α";
  const family = method ? String(method.holm_family_size) : null;
  return [
    {
      title: "1 · The data",
      lead: "What is counted, and the three rates every comparison uses.",
      entries: [
        {
          id: "content-unit",
          term: "Content unit",
          plain:
            "One post as the author published it: the opening post plus the follow-up parts the author added under it in the same thread. Follow-up parts come from Threads' reply links, never from posting time. Replies to followers are left out. The landing page calls a content unit a “post”.",
        },
        {
          id: "snapshot",
          term: "Snapshot",
          plain:
            "One collection of the channel's metrics from the Threads API, taken several times a day. Medians, dots and each content unit's rate use the latest snapshot; the tests use the snapshot they ran on, shown next to them.",
        },
        {
          id: "recorded-views",
          term: "Recorded views",
          plain:
            "The view count Threads reports for the opening post. Every rate is measured on the opening post, so likes or replies on follow-up parts are not counted. A content unit with no recorded views is left out of every rate: missing data is not 0%.",
        },
        {
          id: "rates",
          term: "Engagement, share and conversation rate",
          plain: "Three rates per 100 views. They share one denominator, the opening post's views.",
          formula: [
            "engagement rate   = (likes + replies + reposts + quotes) ÷ views × 100",
            "share rate        = (reposts + quotes) ÷ views × 100",
            "conversation rate = replies ÷ views × 100",
          ],
        },
        {
          id: "median",
          term: "Median, IQR, n",
          plain:
            "The median is the middle rate of a group: half its content units are above, half below. The middle half runs from Q1 to Q3; its width, Q3 − Q1, is the interquartile range (IQR), and this page shows the range itself. n is how many content units with recorded views a number is based on.",
          formula: ["middle half = [Q_1, Q_3]   (25th and 75th percentiles, linear interpolation)"],
          where: [
            "Medians resist outliers: one breakout content unit moves a mean a lot and a median very little.",
          ],
        },
      ],
    },
    {
      title: "2 · Finding topics",
      lead: "Five steps, all on the text alone: no predefined categories, and no views or interactions.",
      entries: [
        {
          id: "embedding",
          term: "Embedding, cosine similarity",
          plain:
            "A multilingual language model turns each content unit's text into a vector. The model is trained so that texts with similar meaning, in Vietnamese, French or English, get vectors pointing in similar directions. Cosine similarity measures that direction.",
          formula: ["e = model(text),  e in R^d,  ||e|| = 1", "cos(a, b) = a · b ÷ (||a|| ||b||)  =  a · b  when ||a|| = ||b|| = 1"],
          where: [
            <>
              <Mono>d</Mono>: the vector&apos;s length (its number of dimensions).
            </>,
            <>
              <Mono>cos</Mono> runs from −1 to 1; 1 means the same direction, so the same meaning to the model.
            </>,
          ],
          thisRun: run ? (
            <>
              Model <Mono>{run.model_id}</Mono>
              {run.embedding_dim ? (
                <>
                  , <Mono>d = {count(run.embedding_dim)}</Mono>
                </>
              ) : null}
              , on the full text of each content unit.
            </>
          ) : null,
        },
        {
          id: "umap",
          term: "UMAP (dimension reduction)",
          plain: `Clustering works poorly on very long vectors, so UMAP first compresses each one to ${dims ?? "a few"} numbers. It links each content unit to its nearest neighbours, then places the points so those links are kept. The map on this page draws exactly these numbers.`,
          formula: [
            `R^d → R^${dims ?? "k"}`,
            "minimise  Σ_ij [ w_ij log(w_ij ÷ v_ij) + (1 − w_ij) log((1 − w_ij) ÷ (1 − v_ij)) ]",
          ],
          where: [
            <>
              <Mono>w_ij</Mono>: how strongly <Mono>i</Mono> and <Mono>j</Mono> are neighbours in the original
              vectors.
            </>,
            <>
              <Mono>v_ij</Mono>: the same in the compressed layout. The sum is small when the layout keeps the
              original neighbours (cross-entropy, McInnes et al. 2018).
            </>,
            "UMAP keeps neighbours, not global distances: two far-apart topics are not necessarily more different.",
          ],
          thisRun:
            neighbours || dims || umapSeed ? (
              <>
                {dims ? <Mono>n_components = {dims}</Mono> : null}
                {neighbours ? (
                  <>
                    {" "}
                    · <Mono>n_neighbors = {neighbours}</Mono> (how many neighbours each point keeps)
                  </>
                ) : null}
                {umapSeed ? (
                  <>
                    {" "}
                    · <Mono>random_state = {umapSeed}</Mono> (fixed, so the same text gives the same map)
                  </>
                ) : null}
                ; other settings are the library defaults.
              </>
            ) : null,
        },
        {
          id: "hdbscan",
          term: "HDBSCAN (clustering)",
          plain:
            "HDBSCAN finds groups of points that sit densely together in the compressed space. It does not need the number of topics in advance. Points in no dense group are left out as noise (“unclustered”) instead of being forced into a topic.",
          formula: [
            "core(x) = distance from x to its k-th nearest neighbour  (x itself counts as the first)",
            "d_mreach(a, b) = max( core(a), core(b), d(a, b) )",
          ],
          where: [
            "Mutual reachability distance pushes points in sparse areas away from everything, so they end up as noise.",
            "HDBSCAN links all points by these distances, cuts the links from the longest down, and keeps the groups that survive with enough members.",
            <>
              <Mono>d</Mono>: straight-line (Euclidean) distance in the compressed space. <Mono>k</Mono> is left
              at the library default, equal to the minimum topic size.
            </>,
          ],
          thisRun:
            minCluster || selection ? (
              <>
                {minCluster ? (
                  <>
                    <Mono>min_cluster_size = {minCluster}</Mono> (the smallest group that counts as a topic)
                  </>
                ) : null}
                {selection ? (
                  <>
                    {minCluster ? " · " : ""}
                    <Mono>cluster_selection_method = {selection}</Mono>
                    {selection === "leaf" ? " (keeps the finest groups, so more and smaller topics)" : ""}
                  </>
                ) : null}
                .
              </>
            ) : null,
        },
        {
          id: "similarity",
          term: "Centre, similarity to centre",
          plain:
            "A topic's centre is the average direction of its content units' vectors. Similarity to centre says how typical a content unit is of its topic. The representatives shown for a topic are the content units with the highest similarity.",
          formula: ["c_t = mean(e_i, i in t) ÷ ||mean(e_i, i in t)||", "similarity(i, t) = e_i · c_t"],
          where: [
            <>
              Computed on the full vectors (<Mono>e</Mono>), not on the compressed map.
            </>,
            "At most 1. It is a cosine, not a probability.",
          ],
        },
        {
          id: "keywords",
          term: "Keywords (c-TF-IDF)",
          plain:
            "Words frequent in this topic but rare in the others: characteristic words, not simply the most frequent ones. Vietnamese text is first split into words (a Vietnamese word can have several syllables), and common function words (“và”, and; “de”, of; “the”…) are removed.",
          formula: ["W(w, t) = tf(w, t) · log(1 + A ÷ f(w))"],
          where: [
            <>
              <Mono>tf(w, t)</Mono>: count of word <Mono>w</Mono> in topic <Mono>t</Mono> ÷ all words in{" "}
              <Mono>t</Mono>.
            </>,
            <>
              <Mono>f(w)</Mono>: count of <Mono>w</Mono> across all topics and the unclustered content units.
            </>,
            <>
              <Mono>A</Mono>: average number of words per group (topics plus unclustered). <Mono>log</Mono> is
              natural.
            </>,
            "A term is a word or a two-word phrase; once a phrase is kept, its single words are not repeated.",
            "A word must appear in at least 2 of the topic's content units; a word found in at least 80% of the topics is dropped (with 3 topics or more). The 8 highest W are kept.",
          ],
          thisRun: param("keyword_segmenter") ? (
            <>
              Word segmentation: <Mono>{param("keyword_segmenter")}</Mono>.
            </>
          ) : null,
        },
        {
          id: "topic",
          term: "Topic",
          plain:
            "A group of content units whose texts sit densely together after compression, as found by HDBSCAN. Content units in no such group are unclustered.",
        },
        {
          id: "topic-name",
          term: "Topic name",
          plain:
            "Written afterwards by Claude (Anthropic's AI model) from the text of up to 15 content units nearest the centre. The name helps reading and plays no part in any test. A topic is renamed only when it is new, was split or merged, has drifted away from its original content, or was named with an older version of the naming prompt or model.",
        },
      ],
    },
    {
      title: "3 · Quality and stability of the topics",
      lead: "How well separated today's topics are, and how much they changed since the previous run.",
      entries: [
        {
          id: "dbcv",
          term: "DBCV (density-based clustering validation)",
          plain:
            "Density-Based Clustering Validation: for each topic, compares how loose the topic is inside with how far it sits from the nearest other topic. Unclustered content units count in the total, so a lot of noise lowers the score.",
          formula: ["V(t) = (sep(t) − spread(t)) ÷ max(sep(t), spread(t))", "DBCV = Σ_t (|t| ÷ n) · V(t)"],
          where: [
            <>
              <Mono>spread(t)</Mono>: the longest edge of the minimum spanning tree that links{" "}
              <Mono>t</Mono>&apos;s points, in mutual reachability distance (DBCV uses its own density-based core
              distance).
            </>,
            <>
              <Mono>sep(t)</Mono>: the smallest such distance between <Mono>t</Mono>&apos;s inner points and those
              of any other topic.
            </>,
            <>
              <Mono>|t|</Mono>: content units in <Mono>t</Mono>; <Mono>n</Mono>: all content units in the run,
              unclustered ones included (Moulavi et al. 2014).
            </>,
            "From −1 to 1, higher is better. There is no standard pass mark, and this page shows only the latest run.",
          ],
          thisRun: dims ? (
            <>
              <Mono>hdbscan.validity.validity_index</Mono> on the {dims} UMAP numbers, not on the full vectors.
            </>
          ) : null,
        },
        {
          id: "ari",
          term: "ARI (Adjusted Rand Index)",
          plain:
            "How much two clusterings agree on which content units belong together, corrected for the agreement expected by chance. 1 means an identical grouping, about 0 no more than chance.",
          formula: [
            "ARI = (Σ_ij C(n_ij, 2) − E) ÷ (1/2 [Σ_i C(a_i, 2) + Σ_j C(b_j, 2)] − E)",
            "E = Σ_i C(a_i, 2) · Σ_j C(b_j, 2) ÷ C(n, 2)",
          ],
          where: [
            <>
              <Mono>n_ij</Mono>: content units in group <Mono>i</Mono> now and group <Mono>j</Mono> in the previous
              run; <Mono>a_i</Mono>, <Mono>b_j</Mono>: group sizes; <Mono>n</Mono>: content units in both runs;{" "}
              <Mono>C(x, 2)</Mono>: number of pairs.
            </>,
            "Two versions: on content units with a topic in both runs, and with unclustered counted as one group.",
            "Only content units present in both runs count, so a run that adds new content units can still score 1.00.",
          ],
        },
        {
          id: "seed",
          term: "Random seed",
          plain:
            "The starting number of a procedure that uses chance. Both seeds on this page are fixed: UMAP's, so the same content units give the same topics, and the permutation test's, so the tests always give the same p-values. Another UMAP seed can draw the topics differently; measuring that (stability across seeds) is still research.",
        },
      ],
    },
    {
      title: "4 · Comparing a topic with the rest of the channel",
      lead: "One test per topic and per rate, then one correction across all of them.",
      entries: [
        {
          id: "rest",
          term: "Rest of the channel",
          plain:
            "Every other content unit in the same clustering run, unclustered ones included. Each topic is compared with this group, not with the channel median (the dashed line is only a reference).",
        },
        {
          id: "cliffs-delta",
          term: "Cliff's δ (effect size)",
          plain:
            "How far apart the two groups are. Pick one content unit from the topic and one from the rest at random: δ is the chance the topic's one has the higher rate, minus the chance it has the lower one.",
          formula: [
            "δ = ( #{(x, y): x > y} − #{(x, y): x < y} ) ÷ (n_topic · n_rest)",
            "share of pairs the topic wins = (1 + δ) ÷ 2   (ties count as half)",
          ],
          where: [
            <>
              <Mono>x</Mono>: a rate in the topic; <Mono>y</Mono>: a rate in the rest; every pair is counted.
            </>,
            "From −1 to +1. 0: neither side tends to be higher. +1: every content unit in the topic beats every content unit in the rest.",
            "δ̂ (delta-hat) is δ computed on this data; a hat (^) marks a value estimated from the data.",
          ],
        },
        {
          id: "brunner-munzel",
          term: "Brunner-Munzel permutation test (p-value)",
          plain:
            "The test behind each p-value. It asks whether a random content unit from the topic is more likely to beat one from the rest than to lose to it. Unlike a t-test, it does not assume bell-shaped data or equal spread, which suits skewed rates.",
          formula: [
            "π = P(rest > topic) + 1/2 P(tie),   estimated from ranks as π̂",
            "T = (π̂ − 1/2) ÷ SE",
            "k_{+} = #{T* ≥ T},   k_{−} = #{T* ≤ T}",
            "p = min(1, 2 · min(k_{+} + 1, k_{−} + 1) ÷ (B + 1))",
          ],
          where: [
            <>
              <Mono>π̂ = (1 − δ̂) ÷ 2</Mono>; with no difference, <Mono>π = 1/2</Mono>.
            </>,
            <>
              <Mono>SE</Mono>: its standard error, from each group&apos;s own spread of ranks (so unequal spreads
              are allowed).
            </>,
            <>
              <Mono>T*</Mono>: the same statistic after reshuffling which content units belong to the topic;{" "}
              <Mono>B</Mono> reshuffles. p is two-sided: a topic can stand out above or below.
            </>,
            "A small p means a gap this large would be rare if topic and rest did not differ.",
          ],
          thisRun: method ? (
            <>
              <Mono>B = {count(method.n_permutations)}</Mono> reshuffles, seed <Mono>{method.random_seed}</Mono>.
              A topic with a single content unit gets its p from a Mann-Whitney test instead; it is always too
              small to conclude.
            </>
          ) : null,
        },
        {
          id: "ci",
          term: "95% CI of δ (unadjusted)",
          plain:
            "The range of δ values the data are compatible with. It comes from the same reshuffles (inverting the test, Pauly et al. 2016). “Unadjusted” means it is not corrected for the number of tests: it shows how precise δ is, not whether the topic stands out.",
          formula: ["low  = δ̂ + 2 · q_{0.025} · SE", "high = δ̂ + 2 · q_{0.975} · SE   (both clipped to [−1, 1])"],
          where: [
            <>
              <Mono>q</Mono>: the 2.5th and 97.5th percentiles of the reshuffled <Mono>T*</Mono>.
            </>,
            "Missing when the groups do not overlap at all (δ = ±1), when every value is equal, or when a group is too small for the test.",
          ],
        },
        {
          id: "holm",
          term: "Holm correction",
          plain: `With ${family ?? "many"} tests, some small p-values appear by chance alone. Holm's method raises the p-values step by step so that the chance of even one false alarm across all the tests stays at ${method ? `${Math.round(method.conclusion_alpha * 1000) / 10}%` : "α"} or less.`,
          formula: [
            "sort p_(1) ≤ p_(2) ≤ … ≤ p_(m)",
            "Holm p_(i) = max over j ≤ i of  min(1, (m − j + 1) · p_(j))",
          ],
          where: [
            <>
              <Mono>{family ? `m = ${family}` : "m"}</Mono>: every topic × the three rates with a p-value, small topics included.
            </>,
            "The smallest p is multiplied by m, the next by m − 1, and so on; the max keeps the order.",
            "It holds even though the tests reuse the same content units (they are not independent).",
          ],
        },
        {
          id: "result",
          term: "Result of a row",
          plain: `How each row of the tests table is labelled.`,
          where: [
            `▲ / ▼ **Stood out above / below** — corrected p below ${alpha}, and at least ${minPosts} content units with recorded views on both sides. Above or below follows the sign of δ.`,
            `● **Not significant after correction** — corrected p of ${alpha} or more. The data cannot show a gap; that is not proof there is none.`,
            `◌ **Too few content units (n < ${minPosts}): not concluded** — the topic or the rest has fewer than ${minPosts} content units with recorded views. Its p still counts in the correction, but it is never concluded.`,
            "— **Not tested** — no p-value could be computed (for example, the topic has no content units with recorded views).",
          ],
        },
        {
          id: "lead",
          term: "Lead vs finding",
          plain:
            "A lead passes the corrected test on today's topics. It becomes a finding only once it also passes a stability rule across random seeds; that rule is not set yet, so a result here is at most a lead.",
        },
        {
          id: "stood-out",
          term: "Stood out in k of m",
          plain: `Of the m clusterings in which a topic had enough content units to test, the k in which it stood out with corrected p below ${alpha} (▲ above, ▼ below).`,
          where: [
            "A clustering is one grouping of the content units; daily runs that give exactly the same grouping count once.",
            "A dash (—) means the topic has never had enough content units to test.",
            "A record, not a stability rule: the clusterings share most of their content units.",
          ],
        },
      ],
    },
  ];
}

export function TopicMethods({
  run,
  method,
  minPosts,
}: {
  run: ClusterRun | null;
  method: ComparisonMethod | null;
  minPosts: number;
}) {
  return (
    <Section
      id="terms"
      n="06"
      short={sectionShort("terms")}
      title="How every number on this page is computed"
      purpose="Each term, its formula and what each symbol means, in the order the page uses them."
    >
      <div className="flex flex-col gap-2">
        <p className={`m-0 ${TYPE.measure} ${TYPE.body}`}>
          Every term means exactly this everywhere on the page; symbols are defined in the entry that uses them. Values marked “this run” are read from the latest
          clustering run and the latest tests.
        </p>
      </div>
      {groups(run, method, minPosts).map((group) => (
        <div key={group.title} className="flex flex-col gap-2 border-t border-border-hairline pt-7">
          <div className="flex flex-col gap-1">
            <h3 className={`m-0 ${TYPE.h3}`}>{group.title}</h3>
            <p className={`m-0 ${TYPE.note}`}>{group.lead}</p>
          </div>
          <dl className="m-0 flex flex-col">
            {group.entries.map((entry) => (
              <div
                key={entry.id}
                id={`term-${entry.id}`}
                className="grid scroll-mt-24 grid-cols-1 gap-x-8 gap-y-2 border-b border-bg-surface py-4 last:border-b-0 md:grid-cols-[220px_minmax(0,1fr)]"
              >
                <dt className={TYPE.h4}>{entry.term}</dt>
                <dd className="m-0 flex flex-col gap-2.5">
                  <p className={`m-0 ${TYPE.measure} ${TYPE.body} [text-wrap:pretty]`}>{entry.plain}</p>
                  {entry.formula ? (
                    // xuống dòng được ở khổ hẹp — không thanh cuộn lồng (luật bố cục)
                    <div className="flex w-full flex-col gap-0.5 rounded-lg border border-border-hairline bg-bg-sunken px-3.5 py-2.5">
                      {entry.formula.map((line) => (
                        <Formula key={line}>{line}</Formula>
                      ))}
                    </div>
                  ) : null}
                  {entry.where && entry.where.length > 0 ? (
                    <ul className={`m-0 flex ${TYPE.measure} list-disc flex-col gap-1 pl-5 text-[13px] leading-[1.55] text-text-secondary marker:text-text-muted`}>
                      {entry.where.map((item, i) => (
                        <li key={i}>{rich(item)}</li>
                      ))}
                    </ul>
                  ) : null}
                  {entry.thisRun ? (
                    <p className={`m-0 ${TYPE.measure} text-[13px] leading-[1.55] text-text-secondary`}>
                      <span className="font-semibold text-text-primary">This run: </span>
                      {entry.thisRun}
                    </p>
                  ) : null}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </Section>
  );
}
