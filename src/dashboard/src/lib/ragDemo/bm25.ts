// BM25 của trang demo RAG, chạy trong trình duyệt (ADR-0037 D3, ADR-0038, ADR-0039).
// Chỉ import file cùng thư mục và chỉ dùng cú pháp TypeScript xoá được: test Python chạy đúng file này
// bằng `node --experimental-strip-types` để đối chiếu với `bm25s` (tests/rag_demo/).
import { rankBm25, slider } from "./rank.ts";
import type { RankedChunk } from "./rank.ts";

// Mặc định của Lucene BM25Similarity, SQLite FTS5 cố định cùng giá trị (nguồn trong ADR-0038).
export const BM25_K1 = 1.2;
export const BM25_B = 0.75;

// Ký tự đi kèm emoji thuộc nhóm dấu: không bỏ thì dính vào chữ đứng trước và làm câu không dấu bị coi là có dấu.
// Khung số (1️⃣) đổi thành khoảng trắng để từ dính sau nó không gộp vào số.
const EMOJI_KEYCAP = /\uFE0F?\u20E3/gu;
const EMOJI_STYLE_MARKS = /[\uFE00-\uFE0F]/gu;

// Số thập phân chỉ áp cho token toàn số; token phải mở đầu bằng chữ hoặc số.
const TOKEN_PATTERN = /\p{N}+(?:[.,]\p{N}+)+|[\p{L}\p{N}][\p{L}\p{M}\p{N}]*/gu;

// Gộp 2 cách đặt dấu thanh ở cụm oa, oe, uy về dấu trên nguyên âm đầu (`tuỳ` = `tùy`), cùng chiều với
// `src/processing/text.py`, thêm cụm oe vì bài thật có "khỏe". Khác text.py: chỉ ở cuối token và không
// sau `q`, để giữ nguyên `hoàng`, `quý`, `poésie`.
const TONE_ON_LAST_VOWEL = /(?<!q)(?:o[àáảãạèéẻẽẹ]|u[ýỳỷỹỵ])$/u;
const TONE_ON_FIRST_VOWEL: Record<string, string> = {
  oà: "òa",
  oá: "óa",
  oả: "ỏa",
  oã: "õa",
  oạ: "ọa",
  oè: "òe",
  oé: "óe",
  oẻ: "ỏe",
  oẽ: "õe",
  oẹ: "ọe",
  uỳ: "ùy",
  uý: "úy",
  uỷ: "ủy",
  uỹ: "ũy",
  uỵ: "ụy",
};

// Token theo âm tiết, không stopword; giữ số như `1,0`; dấu gạch và dấu nháy tách token (ADR-0038 D3, ADR-0039 D4).
export function tokenize(text: string): string[] {
  const visible = text.replace(EMOJI_KEYCAP, " ").replace(EMOJI_STYLE_MARKS, "");
  const normalized = visible.normalize("NFC").toLowerCase().normalize("NFC");
  const tokens = normalized.match(TOKEN_PATTERN) ?? [];
  return tokens.map((token) =>
    token.replace(TONE_ON_LAST_VOWEL, (cluster) => TONE_ON_FIRST_VOWEL[cluster] ?? cluster),
  );
}

// `đ` không có dấu tách rời trong Unicode nên NFD không bỏ được, phải đổi tay.
export function foldToken(token: string): string {
  return token.replaceAll("đ", "d").normalize("NFD").replace(/\p{Mn}/gu, "").normalize("NFC");
}

export type Bm25Index = {
  termCounts: Map<string, number>[];
  docFrequency: Map<string, number>;
  lengths: number[];
  averageLength: number;
};

export function buildIndex(docs: string[][]): Bm25Index {
  const docFrequency = new Map<string, number>();
  const termCounts = docs.map((doc) => {
    const counts = new Map<string, number>();
    for (const term of doc) counts.set(term, (counts.get(term) ?? 0) + 1);
    for (const term of counts.keys()) docFrequency.set(term, (docFrequency.get(term) ?? 0) + 1);
    return counts;
  });
  const lengths = docs.map((doc) => doc.length);
  const total = lengths.reduce((sum, length) => sum + length, 0);
  return {
    termCounts,
    docFrequency,
    lengths,
    averageLength: docs.length > 0 ? total / docs.length : 0,
  };
}

// IDF của Lucene: cộng 1 trong log nên luôn dương, từ có trong quá nửa số đoạn vẫn không âm.
export function inverseDocumentFrequency(docCount: number, docFrequency: number): number {
  return Math.log(1 + (docCount - docFrequency + 0.5) / (docFrequency + 0.5));
}

// Tham số BM25 từ thanh kéo (số nguyên phần trăm): 1 − b tính sẵn là (100 − i) / 100 (ADR-0041 Luật chung 5).
export type Bm25Params = { k1: number; b: number; oneMinusB: number };

export function bm25Params(k1Hundredths: number, bHundredths: number): Bm25Params {
  const b = slider(bHundredths);
  return { k1: slider(k1Hundredths, 0, 300).value, b: b.value, oneMinusB: b.complement };
}

// Vị trí thanh kéo của BM25_K1, BM25_B (test kiểm hai cách viết ra cùng số).
export const DEFAULT_BM25 = bm25Params(120, 75);

// Tử số không có (k1 + 1), bằng đúng điểm `bm25s` `method="lucene"` (ADR-0038 D1).
export function scoreDocs(index: Bm25Index, query: string[], params: Bm25Params): number[] {
  const docCount = index.termCounts.length;
  const { k1, b, oneMinusB } = params;
  return index.termCounts.map((counts, doc) => {
    const lengthNorm = oneMinusB + (b * index.lengths[doc]) / index.averageLength;
    return query.reduce((score, term) => {
      const frequency = counts.get(term);
      if (frequency === undefined) return score;
      const idf = inverseDocumentFrequency(docCount, index.docFrequency.get(term) ?? 0);
      return score + (idf * frequency) / (frequency + k1 * lengthNorm);
    }, 0);
  });
}

export type ChunkIndex = { accented: Bm25Index; folded: Bm25Index };

export function buildChunkIndex(chunks: string[]): ChunkIndex {
  const docs = chunks.map(tokenize);
  return {
    accented: buildIndex(docs),
    folded: buildIndex(docs.map((doc) => doc.map(foldToken))),
  };
}

export type Bm25Result = {
  mode: "accented" | "folded";
  query: string[];
  scores: number[]; // điểm thô của MỌI chunk trong kho (kể cả chunk bị lọc), chưa làm tròn
  ranked: RankedChunk[];
};

// Câu có ít nhất một chữ có dấu so khớp bản có dấu, câu không dấu so khớp bản bỏ dấu (ADR-0038 D3).
// `candidates` = chunk còn lại sau lọc metadata: chỉ loại đoạn, IDF và độ dài trung bình vẫn của cả kho
// (ADR-0041, bảng từng bước).
export function searchBm25(
  index: ChunkIndex,
  question: string,
  params: Bm25Params = DEFAULT_BM25,
  candidates?: readonly number[],
): Bm25Result {
  const tokens = tokenize(question);
  const accented = tokens.some((token) => foldToken(token) !== token);
  const query = accented ? tokens : tokens.map(foldToken);
  const scores = scoreDocs(accented ? index.accented : index.folded, query, params);
  return {
    mode: accented ? "accented" : "folded",
    query,
    scores,
    ranked: rankBm25(scores, candidates),
  };
}
