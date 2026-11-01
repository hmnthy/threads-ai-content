// Thang chữ của toàn sản phẩm (design-system §3) — một hằng cho mọi trang. File thường (không "use client"): server
// component (các section landing) import từ đây; hằng xuất từ một module "use client" chỉ là tham chiếu phía server,
// đọc ra `undefined` (ADR-0032). AppBlock.tsx re-export cho component client.
// Mảnh trình bày dùng chung của mọi trang (landing lấy vai từ đây — design-system §3b C2). Thứ bậc chữ
// (Thy 2026-10-29, lần bác thứ 2: "headline / title khối thì bé, còn chữ nội dung thì lớn, dựa trên logic
// gì?") — tiêu đề LUÔN lớn hơn nội dung nó dẫn, để người đọc nhanh quét theo tiêu đề mà không sót khối
// (design-system §3, thang chung của sản phẩm — landing chỉ thêm display-1/2, ADR-0029):
//   40px w700  h1 tiêu đề trang (đầu trang căn giữa)
//   26px w700  h2 tiêu đề khối (kèm số thứ tự + dòng mục đích + kẻ đậm dưới)
//   20px w600  h3 tiêu đề mục trong khối
//   18px w600  câu trả lời của khối, trong khung nhấn
//   28px w700  số chính trong hộp Key numbers (vai metric, tabular — ADR-0030 K2)
//   17px w600  h4 tiêu đề hộp con (Key numbers, How it is computed, Limits…)
//   15px       thân bài, gạch đầu dòng, nhãn hàng của bảng số · nhãn dưới số trong hộp Key numbers (w600)
//   13px       chữ trong ô bảng, ghi chú phụ
//   12.5px     mono: công thức, số trong bảng — chỉ mono
//   12px w600  header cột bảng, nhãn nhỏ (eyebrow "Answer")
//   0.8em      chỉ số dưới/trên trong Formula (≈ 10px) — không dùng ngoài công thức
export const TYPE = {
  h2: "text-[26px] font-bold leading-[1.25] tracking-[-0.02em] text-text-primary",
  h3: "text-[20px] font-semibold leading-[1.3] tracking-[-0.01em] text-text-primary",
  h4: "text-[17px] font-semibold leading-[1.4] text-text-primary",
  answer: "text-[18px] font-semibold leading-[1.45] text-text-primary",
  body: "text-[15px] leading-[1.6] text-text-secondary",
  bodyStrong: "text-[15px] font-semibold leading-[1.45] text-text-primary",
  cell: "text-[13px] leading-[1.45]",
  note: "text-[13px] leading-[1.55] text-text-secondary",
  mono: "font-mono text-[12.5px] leading-[1.7] tabular-nums",
  label: "text-[12px] font-medium leading-[1.5] text-text-muted",
  th: "text-[12px] font-semibold text-text-secondary",
  metric: "text-[28px] font-bold leading-[1.15] tracking-[-0.02em] tabular-nums text-text-primary",
  eyebrow: "text-[12px] font-semibold tracking-[0.06em] text-text-muted",
  // Nút chính của trang giới thiệu (hero + CTA cuối của landing) — vai riêng 15px w600 (Thy 2026-11-01, ADR-0032):
  // nút 13px trông yếu trên landing; mọi nút / tab / pill khác vẫn là control 13px
  cta: "text-[15px] font-semibold",
  // eyebrow có số, amber (số khối, "01 · Problem" của section landing) — chỉ mono 12.5
  eyebrowNum: "font-mono text-[12.5px] font-semibold",
  // Thy 2026-10-29: chữ chạy hết bề rộng khung chứa — không chừa khoảng trắng bên phải (bỏ giới hạn 72ch)
  measure: "",
} as const;
