// Dữ liệu hiển thị của landing (tầng B) — dựng từ API thật, không số nào gõ cứng
// (docs/design/landing-handoff.md §0, §4). Chỉ đếm, sắp xếp và đổi đơn vị hiển thị ở đây;
// median/IQR/n/cờ insufficient_data luôn lấy từ backend (UI-L20260903-small-n-flag).
import type {
  AnalyticsOverview,
  ComparisonHistory,
  ComparisonMethod,
  ContentUnit,
  DistributionStats,
  PipelineSummary,
  Topic,
  TopicComparisonRow,
  TopicComparisons,
} from "@/lib/api";

// Bài minh hoạ của hero — lựa chọn thiết kế của mockup (post 17939285085325700), không phải số liệu
export const HERO_POST_ID = "17939285085325700";
export const HERO_QUESTION =
  'Did "8 kinh nghiệm sau 8 năm ở Pháp" (8 lessons from 8 years in France) do better than the channel\'s usual post?';

// Danh từ gọi đơn vị phân tích: landing gọi "post" (định nghĩa 1 lần ở "How it solves"), trang
// /topics hiện đúng thuật ngữ "content unit" kèm định nghĩa (Thy chốt 2026-10-29)
export interface Noun {
  one: string;
  many: string;
}
export const POST_NOUN: Noun = { one: "post", many: "posts" };
export const UNIT_NOUN: Noun = { one: "content unit", many: "content units" };

export interface TopicView {
  id: string;
  name: string;
  description: string | null;
  postCount: number;
  keywords: string[];
  representatives: { id: string; text: string; similarity: number | null }[];
  stats: DistributionStats;
  excluded: number;
  rates: number[]; // engagement % của các bài đo được trong topic (chấm trên strip)
  // ADR-0018 + ADR-0023 1e: ngày đặt tên (UTC) + số lần gom cụm liền gần nhất giữ tên
  labeledAt: string | null;
  labelModel: string | null;
  runsKeepingLabel: number;
}

export interface HeroPost {
  id: string;
  rate: number;
  firstLine: string;
  topicId: string | null;
  similarity: number | null;
  nearestToCentre: boolean; // bài đứng đầu danh sách bài gần tâm của topic
}

export interface LandingData {
  snapshotDate: string | null;
  firstPostAt: string | null; // bài sớm nhất trong DB — "since <tháng năm>" (không nói "toàn lịch sử")
  axisMax: number; // biên phải trục engagement % của mọi strip
  channel: {
    rates: number[];
    stats: DistributionStats;
    excluded: number;
    total: number; // bài đo được + bài bị loại (mẫu số của dòng loại)
  };
  hero: HeroPost | null;
  heroFound: boolean; // bài hero có trong DB (dù chưa có views) — để báo đúng lý do khi trống
  topics: TopicView[]; // nhiều bài trước
  // A4: 6 bài không chữ và 6 bài không views là CÙNG 6 bài? Code không bảo đảm điều đó
  // (UI-0011-two-exclusions) nên chỉ gộp thành 1 dòng khi kiểm thấy 2 tập trùng nhau
  sameExcludedPosts: boolean;
  noise: { rates: number[]; stats: DistributionStats | null; excluded: number };
  mapPoints: { x: number; y: number; topicId: string | null }[]; // UMAP dim 1–2, chuẩn hoá 0–100
  summary: PipelineSummary;
  // Kiểm định engagement theo topic (ADR-0023), tính trong job NLP: null khi chưa có kết quả nào
  // hoặc không tải được. Mô tả (median/IQR/chấm) ở trên vẫn đọc dữ liệu mới nhất; kiểm định mang
  // mốc giờ riêng (`computedAt`, `snapshotAsOf`). `stale` → API đã ẩn δ/p (Thy chốt D3).
  topicTests: TopicTests | null;
  // Tách 2 lý do `topicTests` null: endpoint lỗi ("unavailable") hay API chạy tốt nhưng chưa có lần
  // kiểm định nào ("not-run", `method` null) — UI nói đúng lý do, không bảo "reload" khi chưa chạy
  topicTestsStatus: "loaded" | "not-run" | "unavailable";
}

export interface TopicTests {
  computedAt: string | null;
  snapshotAsOf: string | null;
  stale: boolean;
  method: ComparisonMethod;
  history: ComparisonHistory | null;
  engagement: Record<string, TopicComparisonRow>; // topic id → dòng engagement
  rows: TopicComparisonRow[]; // mọi dòng (topic × 3 chỉ số + nhiễu + kênh) — bảng đủ họ Holm ở /topics
}

// Phần ngoặc "(11 topics × 3 rates)" chỉ khi họ Holm đúng bằng số topic × 3 chỉ số: topic không có
// p nào (n đo được = 0) đứng ngoài họ (ADR-0023 1c) — 1 helper cho mọi câu nêu số phép so
export function familyBreakdown(tests: TopicTests, topicCount: number): string {
  return tests.method.holm_family_size === topicCount * 3 ? `${topicCount} topics × 3 rates` : "";
}

// Câu "vì sao không topic nào được nêu tên" (Thy 2026-10-29: không đạt thì phải giải thích, không
// ẩn). Chỉ đọc số từ API: p trước/sau hiệu chỉnh của dòng engagement có p thô nhỏ nhất (trong các
// topic đủ bài), kích thước họ Holm, cỡ topic nhỏ nhất/lớn nhất. Không tự tính p hay power.
// Trả từng câu (UI vẽ thành khối "Why no topic is named yet" riêng, không chìm trong dòng phụ).
export function noneStandOutReason(
  tests: TopicTests,
  topics: TopicView[],
  noun: Noun,
  smallLook = "faded", // landing làm mờ dòng ít bài; /topics tô chữ xám ("shown in grey")
  split = false, // /topics: mỗi ý 1 bullet, không dồn 5 số vào 1 câu (copy-reviewer 2026-10-29)
): string[] {
  const alpha = tests.method.conclusion_alpha;
  const family = tests.method.holm_family_size;
  const nameOf = new Map(topics.map((t) => [t.id, t.name]));
  const tested = topics
    .map((t) => tests.engagement[t.id])
    .filter(
      (row): row is TopicComparisonRow =>
        row !== undefined && row.p_value !== null && row.p_value_holm !== null && row.effect_size !== null,
    );
  const comparable = tested.filter((row) => !row.insufficient_data);
  const strongest = comparable.reduce<TopicComparisonRow | null>(
    (best, row) => (best === null || row.p_value! < best.p_value! ? row : best),
    null,
  );
  const sizes = comparable.map((row) => row.group.n);
  const small = tested.length - comparable.length;
  const breakdown = familyBreakdown(tests, topics.length);
  // `split` (/topics): in đậm cụm then chốt bằng `**…**` (AppBlock `rich`); landing giữ chữ trơn
  const b = (text: string) => (split ? `**${text}**` : text);
  const parts = [
    `A topic stands out only if it has at least ${tests.method.min_posts_to_compare} ${noun.many} with recorded views and its p-value is ${b(`still below ${alpha} after correcting`)} for all ${family} tests${breakdown ? ` (${breakdown})` : ""}.`,
  ];
  if (comparable.length === 0) {
    // Mọi topic quá nhỏ: nói thẳng lý do, không để khối trống "large enough" (vacuous)
    parts.push(
      `Every topic has fewer than ${tests.method.min_posts_to_compare} ${noun.many} with recorded views, so none can stand out yet; their p-values still count in the correction.`,
    );
  }
  // "closest call" = p thô nhỏ nhất trong các topic đủ bài (không phải |δ| lớn nhất)
  if (strongest && split) {
    parts.push(
      `The **closest call** (smallest p before correction) is ${nameOf.get(strongest.group_id) ?? strongest.group_id}: its ${noun.many} beat the rest of the channel in about ${winShare(strongest.effect_size!)}% of pairs (Cliff's δ ${signed(strongest.effect_size!)}).`,
      `Its p is ${formatP(strongest.p_value!)} before correction and **${formatP(strongest.p_value_holm!)} after**${strongest.p_value_holm! > alpha ? `, above ${alpha}` : strongest.p_value_holm! === alpha ? `, equal to ${alpha}` : ""}.`,
    );
  }
  if (sizes.length > 0 && split) {
    const lo = Math.min(...sizes);
    const hi = Math.max(...sizes);
    parts.push(
      `Topics large enough to conclude on have ${lo === hi ? lo : `${lo} to ${hi}`} ${noun.many} with recorded views each${
        small > 0 ? `; ${small} smaller ${small === 1 ? "one is" : "ones are"} ${smallLook} and never stand out` : ""
      }.`,
      `With ${family} tests to correct for, groups this small can only show very large gaps.`,
    );
  }
  if (strongest && !split) {
    parts.push(
      `The closest call is ${nameOf.get(strongest.group_id) ?? strongest.group_id}: its ${noun.many} beat the rest of the channel in about ${winShare(strongest.effect_size!)}% of pairs (Cliff's δ ${signed(strongest.effect_size!)}). Its p is ${formatP(strongest.p_value!)} before correction, but ${formatP(strongest.p_value_holm!)} after${strongest.p_value_holm! > alpha ? `, above ${alpha}` : strongest.p_value_holm! === alpha ? `, equal to ${alpha}` : ""}.`,
    );
  }
  if (sizes.length > 0 && !split) {
    const lo = Math.min(...sizes);
    const hi = Math.max(...sizes);
    parts.push(
      // Không quy nguyên nhân cho cỡ mẫu bằng số power tự suy: câu trung tính, đúng theo ADR-0023
      // mục "Sức mạnh thống kê" (cỡ topic hiện tại chỉ phát hiện được chênh lệch rất lớn)
      `The topics large enough to conclude on have ${lo === hi ? lo : `${lo} to ${hi}`} ${noun.many} with recorded views each${
        small > 0 ? `; ${small} smaller ${small === 1 ? "topic is" : "topics are"} ${smallLook} and never stand out` : ""
      }. After a correction for this many tests, groups this small can only show very large gaps.`,
    );
  }
  parts.push(
    split
      ? "So **the data cannot show a difference yet**; that is not the same as showing there is none."
      : "So the data cannot show a difference yet; that is not the same as showing there is none.",
  );
  return parts;
}

// Số phép so có p thô < ngưỡng trong cả họ, đặt cạnh số kỳ vọng nếu không topic nào khác thật
// (α × m — định nghĩa của mức ý nghĩa, không phải hằng số tự đặt; đúng cả khi các phép so phụ thuộc
// nhau nhờ tính tuyến tính của kỳ vọng; với p hoán vị mẫu nhỏ — bảo thủ — chỉ là CẬN TRÊN nên UI
// ghi "at most about"): giải thích vì sao phải hiệu chỉnh
export function rawSignificantCount(tests: TopicTests): { below: number; expected: number } {
  const below = tests.rows.filter(
    (row) => row.kind === "topic" && row.p_value !== null && row.p_value < tests.method.conclusion_alpha,
  ).length;
  return { below, expected: tests.method.conclusion_alpha * tests.method.holm_family_size };
}

// Câu hover lịch sử "k of m" (ADR-0024; chữ Thy duyệt 2026-10-20 sau copy-reviewer + code-reviewer,
// `ui-contract-audit.md`). Hướng + k của ô lấy từ backend (`history.direction`/`stood_out`, có pytest);
// ở đây chỉ dựng câu. N = m + số cách chia thiếu bài = số cách chia ĐÃ KIỂM ĐỊNH topic này ("tested
// on N clusterings") — không phải số cách chia thật (bước so sánh có thể lỗi suốt 1 cách chia). Mệnh
// đề "the current one" đọc kết luận lần kiểm định hiện tại — bỏ khi `stale` (δ/p bị ẩn).
export function historySentence(
  row: TopicComparisonRow | undefined,
  method: ComparisonMethod,
  stale: boolean,
  noun: Noun = POST_NOUN,
): string {
  const history = row?.history;
  if (!history) return "";
  const since = parisDate(history.since);
  const m = history.clusterings;
  const its = `of its ${noun.many}`;
  if (m === 0) return `Since ${since}, this topic has never had enough ${noun.many} to test.`;
  const total = m + history.too_few_posts;
  const tested =
    total === 1
      ? `Since ${since}, this topic has been tested on one clustering`
      : `Since ${since}, this topic has been tested on ${total} clusterings`;
  if (history.higher + history.lower === 0) {
    if (history.too_few_posts === 0) {
      return `${tested} and did not stand out in ${total === 1 ? "it" : "any of them"}.`;
    }
    return m === 1
      ? `${tested}; it had enough ${noun.many} to test in 1 and did not stand out in it.`
      : `${tested}; it had enough ${noun.many} to test in ${m} and stood out in none.`;
  }
  const both = history.higher > 0 && history.lower > 0;
  const where = both
    ? `above the rest of the channel in ${history.higher} and below it in ${history.lower}`
    : `${history.direction === "lower" ? "below" : "above"} the rest of the channel in ${history.stood_out}`;
  if (total === 1) return `${tested} and stood out ${history.direction === "lower" ? "below" : "above"} the rest of the channel in it.`;
  const outOf =
    history.too_few_posts > 0 ? `of the ${m} with enough ${its} to test` : "of them";
  const verdict = stale ? null : testVerdict(row, method);
  if (m === 1) {
    // 1 cách chia đủ bài (+ ≥ 1 cách chia thiếu bài) và topic đã đạt ở đó — tránh "in 1 of the 1"
    // (chữ Thy duyệt 2026-10-20). Lần hiện tại kiểm định được thì chính là lần đạt đó.
    const only = `${tested}: it stood out ${history.direction === "lower" ? "below" : "above"} the rest of the channel in the only one with enough ${its} to test`;
    return verdict === "higher" || verdict === "lower"
      ? `${only}, the current one.`
      : verdict === "too few posts"
        ? `${only}; the current one had too few ${its} to test.`
        : `${only}.`;
  }
  const current =
    verdict === null || verdict === "not tested"
      ? ""
      : verdict === "higher" || verdict === "lower"
        ? `, including the current one${both ? ` (${verdict === "higher" ? "above" : "below"})` : ""}`
        : verdict === "too few posts"
          ? `; the current one had too few ${its} to test`
          : ", but not in the current one";
  return `${tested}: it stood out ${where} ${outOf}${current}.`;
}

// Đánh dấu theo ADR-0023 (p Holm < ngưỡng VÀ đủ bài); ADR-0024: chỉ là gợi ý, không câu khẳng định
export function testVerdict(
  row: TopicComparisonRow | undefined,
  method: ComparisonMethod,
): "higher" | "lower" | "not distinguishable" | "too few posts" | "not tested" {
  if (!row || row.p_value_holm === null || row.effect_size === null) return "not tested";
  if (row.insufficient_data) return "too few posts";
  if (row.p_value_holm >= method.conclusion_alpha) return "not distinguishable";
  return row.effect_size > 0 ? "higher" : "lower";
}

// δ có dấu, 2 chữ số: "+0.62" / "−0.47" (dấu trừ thật, U+2212)
export function signed(value: number): string {
  const text = Math.abs(value).toFixed(2);
  return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text;
}

// p theo mức phân giải của số hoán vị: dưới 0.001 ghi "< 0.001", không ghi số 0 giả
export function formatP(value: number): string {
  return value < 0.001 ? "< 0.001" : value.toFixed(3);
}

export function firstLine(text: string, max = 110): string {
  const line = text.trim().split("\n")[0].trim();
  return line.length > max ? `${line.slice(0, max).trimEnd()}…` : line;
}

export function pct(value: number, digits = 2): string {
  return `${value.toFixed(digits)}%`;
}

export function count(value: number): string {
  return value.toLocaleString("en-US");
}

// run_at lưu UTC → hiển thị Europe/Paris (có giờ mùa hè), luôn kèm nhãn múi giờ (UI-0017-run-time)
export function parisTime(iso: string): string {
  const parts: Record<string, string> = {};
  for (const part of new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso))) {
    parts[part.type] = part.value;
  }
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} Paris time`;
}

// Mốc kiểm định: 1 nhãn "Paris time" cho cả câu, bỏ ngày của mốc dữ liệu khi trùng ngày
// (UI-0017-run-time) — "2026-10-09 at 21:08 on data collected up to 17:18 (Paris time)"
export function testTimes(computedAt: string, dataAsOf: string | null): string {
  const [ranDate, ranTime] = parisTime(computedAt).replace(" Paris time", "").split(" ");
  if (!dataAsOf) return `${ranDate} at ${ranTime} (Paris time)`;
  const [dataDate, dataTime] = parisTime(dataAsOf).replace(" Paris time", "").split(" ");
  const upTo = dataDate === ranDate ? dataTime : `${dataDate} ${dataTime}`;
  return `${ranDate} at ${ranTime} on data collected up to ${upTo} (Paris time)`;
}

// Chỉ ngày theo giờ Paris ("2026-10-12") — mốc bắt đầu lịch sử "k of m" (ADR-0024)
export function parisDate(iso: string): string {
  return parisTime(iso).slice(0, 10);
}

// "A", "A and B", "A, B and C"
export function andList(items: string[]): string {
  return items.length <= 1
    ? (items[0] ?? "")
    : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

// Cách đọc chuẩn của Cliff's δ: (1 + δ) / 2 = tỉ lệ cặp (bài topic, bài khác) mà bài topic thắng,
// cặp hoà tính nửa — δ = P(>) − P(<) nên (1 + δ)/2 = P(>) + ½P(=)
export function winShare(delta: number): number {
  return Math.round(((1 + delta) / 2) * 100);
}

// "April 2025", "7 Oct 2026" — ngày theo Europe/Paris như mọi mốc khác trên trang
export function monthYear(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
}

export function dayMonthYear(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
}

// Thứ hạng so với các bài KHÁC (bài không so với chính nó): số bài thấp hơn và % trên số bài
// còn lại. % làm tròn XUỐNG để câu "higher than X%" luôn đúng — làm tròn gần nhất có thể biến
// 49,7% thành "50%" ở nhánh dưới median và đọc như mâu thuẫn.
export function rankAmongOthers(
  rates: number[],
  rate: number,
): { below: number; others: number; share: number } {
  const below = rates.filter((value) => value < rate).length;
  const others = rates.includes(rate) ? rates.length - 1 : rates.length;
  return { below, others, share: others > 0 ? Math.floor((below * 100) / others) : 0 };
}

export function buildLandingData(
  units: ContentUnit[],
  topics: Topic[],
  overview: AnalyticsOverview,
  summary: PipelineSummary,
  comparisons: TopicComparisons | null = null,
): LandingData {
  const measurable = units.filter((unit) => unit.metrics !== null);
  const rateOf = new Map(measurable.map((unit) => [unit.id, unit.metrics!.engagement_rate]));
  const ratesWhere = (keep: (unit: ContentUnit) => boolean) =>
    measurable.filter(keep).map((unit) => unit.metrics!.engagement_rate);

  const topicViews: TopicView[] = topics
    .filter((topic) => topic.method === "cluster")
    .map((topic) => ({
      id: topic.id,
      name: topic.label_en,
      description: topic.description_en,
      labeledAt: topic.labeled_at,
      labelModel: topic.label_model,
      runsKeepingLabel: topic.runs_keeping_label,
      postCount: topic.post_count,
      keywords: topic.keywords,
      representatives: topic.representatives.map((rep) => ({
        id: rep.id,
        text: firstLine(rep.full_text),
        similarity: rep.centroid_similarity,
      })),
      stats: topic.engagement,
      excluded: topic.excluded_no_views,
      rates: ratesWhere((unit) => unit.topic?.topic_id === topic.id),
    }))
    .sort((a, b) => b.postCount - a.postCount);

  const heroUnit = units.find((unit) => unit.id === HERO_POST_ID);
  const heroRate = heroUnit ? rateOf.get(heroUnit.id) : undefined;
  const heroTopicId = heroUnit?.topic?.topic_id ?? null;
  const hero: HeroPost | null =
    heroUnit && heroRate !== undefined
      ? {
          id: heroUnit.id,
          rate: heroRate,
          firstLine: firstLine(heroUnit.full_text),
          topicId: heroTopicId,
          similarity: heroUnit.topic?.centroid_similarity ?? null,
          nearestToCentre:
            topicViews.find((topic) => topic.id === heroTopicId)?.representatives[0]?.id ===
            heroUnit.id,
        }
      : null;

  // Bài nhiễu = đã embed (có toạ độ UMAP) nhưng không thuộc topic nào
  const noiseRates = ratesWhere((unit) => unit.topic === null && unit.umap !== null);

  const placed = units.filter((unit) => unit.umap !== null);
  const xs = placed.map((unit) => unit.umap![0]);
  const ys = placed.map((unit) => unit.umap![1]);
  const scale = (value: number, values: number[]) => {
    const lo = Math.min(...values);
    const span = Math.max(...values) - lo || 1;
    return ((value - lo) / span) * 100;
  };

  const allRates = measurable.map((unit) => unit.metrics!.engagement_rate);
  const noText = units.filter((unit) => !unit.full_text.trim()).map((unit) => unit.id);
  const noViews = new Set(units.filter((unit) => unit.metrics === null).map((unit) => unit.id));
  const sameExcludedPosts =
    noText.length > 0 &&
    noText.length === summary.units_without_text &&
    noViews.size === overview.excluded_no_views &&
    noText.length === noViews.size &&
    noText.every((id) => noViews.has(id));
  return {
    // ngày theo giờ Paris, cùng múi với mốc "clustered … Paris time" trên trang
    snapshotDate: summary.latest_snapshot_at ? parisTime(summary.latest_snapshot_at).slice(0, 10) : null,
    firstPostAt: units.reduce<string | null>(
      (min, unit) =>
        unit.timestamp && (min === null || unit.timestamp < min) ? unit.timestamp : min,
      null,
    ),
    // trục chung: bài cao nhất + lề 0.2 điểm cho chấm, làm tròn lên bội 0.2 (mockup: 5.6 cho max 5.38)
    axisMax: Math.ceil((Math.max(...allRates, 1) + 0.2) * 5) / 5,
    channel: {
      rates: allRates,
      stats: overview.engagement,
      excluded: overview.excluded_no_views,
      total: overview.post_count + overview.excluded_no_views,
    },
    hero,
    heroFound: heroUnit !== undefined,
    sameExcludedPosts,
    topics: topicViews,
    noise: {
      rates: noiseRates,
      stats: summary.noise_engagement,
      excluded: summary.noise_excluded_no_views,
    },
    mapPoints: placed.map((unit) => ({
      x: scale(unit.umap![0], xs),
      y: scale(unit.umap![1], ys),
      topicId: unit.topic?.topic_id ?? null,
    })),
    summary,
    topicTests:
      comparisons && comparisons.method
        ? {
            computedAt: comparisons.computed_at,
            snapshotAsOf: comparisons.snapshot_as_of,
            stale: comparisons.stale,
            method: comparisons.method,
            history: comparisons.history,
            engagement: Object.fromEntries(
              comparisons.rows
                .filter((row) => row.kind === "topic" && row.metric === "engagement")
                .map((row) => [row.group_id, row]),
            ),
            rows: comparisons.rows,
          }
        : null,
    topicTestsStatus: !comparisons ? "unavailable" : comparisons.method ? "loaded" : "not-run",
  };
}

export interface SwarmDot {
  x: number; // px trong bề rộng `width`
  y: number; // px
  index: number; // vị trí trong mảng giá trị đầu vào
}

// Xếp chấm theo giá trị tăng dần: thử y = tâm, tâm±step, tâm±2step… lấy chỗ đầu tiên không
// chạm chấm đã đặt (khoảng cách ≥ minDist). Hết chỗ thì đặt ở tâm — không bỏ chấm nào.
export function swarm(
  values: number[],
  opts: { width: number; axisMax: number; cy: number; step: number; minDist: number; tries: number },
): SwarmDot[] {
  const order = values.map((value, index) => ({ value, index })).sort((a, b) => a.value - b.value);
  const placed: SwarmDot[] = [];
  for (const { value, index } of order) {
    const x = (value / opts.axisMax) * opts.width;
    let y = opts.cy;
    for (let k = 0; k < opts.tries; k++) {
      const candidate = opts.cy + (k === 0 ? 0 : (k % 2 ? 1 : -1) * Math.ceil(k / 2) * opts.step);
      if (placed.every((p) => (p.x - x) ** 2 + (p.y - candidate) ** 2 >= opts.minDist ** 2)) {
        y = candidate;
        break;
      }
    }
    placed.push({ x, y, index });
  }
  return placed;
}

// Strip 1 hàng (bảng topic, CMI, ô "This post"): toạ độ x theo % để co giãn theo cột
export function rowSwarm(
  values: number[],
  axisMax: number,
  cy: number,
  step: number,
  minDist = 6.5,
  width = 700,
): { left: string; top: string }[] {
  return swarm(values, { width, axisMax, cy, step, minDist, tries: 9 }).map((dot) => ({
    left: `${(dot.x / width) * 100}%`,
    top: `${dot.y}px`,
  }));
}

export function axisPct(value: number, axisMax: number): string {
  return `${(value / axisMax) * 100}%`;
}

export function ticks(axisMax: number): number[] {
  return Array.from({ length: Math.floor(axisMax) + 1 }, (_, i) => i);
}
