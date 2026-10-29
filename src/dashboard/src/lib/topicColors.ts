// Màu + hình định danh mỗi topic trên /topics (bản đồ, danh sách, swatch). Thy 2026-10-29 chấp nhận đa
// sắc thay cho 1 màu nhấn (thay UI-L20260930-topic-single-accent). Luật skill dataviz:
// - 8 màu theo thứ tự cố định (`--cat-1..8`, globals.css), không sinh màu thứ 9;
// - topic thứ 9–16 = màu slot (i − 8) + hình thoi, thứ 17–24 = hình vuông: mã hoá kép màu × hình (tối
//   đa 24 cặp khác nhau; từ topic thứ 25 cặp màu × hình lặp lại — khi đó cần thêm hình), không lặp vòng màu
//   đơn thuần;
// - màu đi theo topic (thứ tự topic từ API, lớn trước), không theo hạng của một phép đo;
// - trên scatter, quá 3 màu không tách được với mọi người đọc mù màu → luôn có nhãn chữ (danh sách,
//   hover) và topic đang chọn được làm nổi; màu chỉ giúp quét nhanh, không mang thông tin một mình.
export const CATEGORICAL_SLOTS = 8;

export type TopicShape = "circle" | "diamond" | "square";

export interface TopicMark {
  slot: number; // 1..8
  cssVar: string; // "var(--cat-n)" cho swatch HTML
  token: string; // "--cat-n" để đọc hex cho Plotly (WebGL không đọc var())
  shape: TopicShape;
}

export function topicMark(index: number): TopicMark {
  const slot = (index % CATEGORICAL_SLOTS) + 1;
  return {
    slot,
    cssVar: `var(--cat-${slot})`,
    token: `--cat-${slot}`,
    shape: index < CATEGORICAL_SLOTS ? "circle" : index < 2 * CATEGORICAL_SLOTS ? "diamond" : "square",
  };
}
