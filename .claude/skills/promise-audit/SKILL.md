---
name: promise-audit
description: Audit how far the Unthreaded landing page's promises (cover) are from what the app pages actually show (interior) — runs the independent promise-auditor subagent, saves a dated report next to the previous ones, and summarises the gap level, its trend and the work packages to do first. Use when Thy asks for it (typically at the end of a work session) or asks how far the landing and the dashboard pages have drifted apart.
argument-hint: "[optional note for the summary, never passed to the auditor]"
---

# /promise-audit — Bìa (landing) so với ruột (các trang app)

Ghi chú của Thy (chỉ dùng ở Bước 4, **không** chuyển cho agent): **$ARGUMENTS**

Lần quét nào cũng phủ **toàn bộ** landing và mọi trang app. Không có quét một phần: báo cáo một phần làm độ phủ và
danh sách id của lần sau so sai.

!`git rev-parse --short HEAD`
!`git branch --show-current`
!`git worktree list --porcelain`

Đọc 3 dòng trên như sau:
- Dòng 1 là commit đang kiểm.
- Dòng 2 là nhánh. Dòng này rỗng nghĩa là detached HEAD (đang đứng ở một commit lẻ, không trên nhánh nào).
- Trong danh sách worktree, mục `worktree …` **đầu tiên** là thư mục chính (gọi là `<main>`).

## Bước 1 — Chuẩn bị (không tự kết luận gì)

1. **Nơi lưu** là `data/audits/promise-gap/` của **checkout đang đứng** (gọi là `<here>`).
   - Thư mục này bị gitignore: báo cáo riêng tư, không lên repo public, không cần PR (Pull Request — đề nghị gộp nhánh).
   - Không ghi sang checkout khác: phiên đang trong worktree bị chặn ghi ra ngoài worktree của nó.
   - Khi dọn một worktree, `/wt clean` gom báo cáo của nó về `<main>`.
2. **Kiểm gitignore trước khi ghi**: `git check-ignore -q data/audits/promise-gap/x.md`. Lệnh trả mã khác 0 nghĩa là
   checkout này chưa có dòng `data/audits/` trong `.gitignore`, ví dụ nhánh tạo trước khi luật này vào `main`. Khi đó
   **không ghi file**: đưa báo cáo cho Thy trong câu trả lời và nói rõ lý do.
3. **Báo cáo lần trước**:
   - Gom mọi `<worktree>/data/audits/promise-gap/*.md`, quét qua **mọi** worktree trong danh sách trên bằng Glob. Tên
     file có dạng `<YYYY-MM-DD>-<NN>-<sha>.md`, nên sắp theo tên là ra đúng thứ tự thời gian.
   - Đi từ file mới nhất trở về trước. Chọn file đầu tiên có `<sha>` là tổ tiên của HEAD, kiểm bằng
     `git merge-base --is-ancestor <sha> HEAD` (mã 0 là tổ tiên), mỗi file một lệnh. Lý do: so hai nhánh chưa gộp như
     thể hai thời điểm sẽ cho ra lời hứa "đã khép" hay "nặng lên" ảo.
   - Không file nào là tổ tiên của HEAD thì lấy file mới nhất, và báo cho cả agent lẫn Thy là hai bản nằm trên hai dòng
     lịch sử khác nhau.
   - Glob vào một worktree bị chặn thì bỏ qua worktree đó, và báo Thy là phần so sánh có thể thiếu.
4. **Danh sách id lần trước**: từ bảng đầy đủ (mục 4) của báo cáo lần trước, chép **chỉ** 3 cột id · loại · lời hứa.
   Không chép kết luận, mức hay chi phí.
5. Nhánh khác `main`, hoặc detached HEAD, nghĩa là đang kiểm code chưa phải bản live. Phải nói rõ khi báo lại cho Thy.

## Bước 2 — Gọi agent độc lập

Gọi `@agent-promise-auditor` với prompt **chỉ** gồm:
- commit, nhánh, đường dẫn tuyệt đối của `<here>`;
- DB thật: đường dẫn tuyệt đối `<main>/data/threads.db`. Agent mở nó chỉ-đọc theo đoạn lệnh mẫu trong hướng dẫn của
  agent. File không tồn tại thì ghi "không có DB";
- đường dẫn báo cáo lần trước, kèm commit và nhánh của nó, kèm danh sách id lần trước (Bước 1.4). Hai bản khác dòng
  lịch sử (Bước 1.3) thì ghi rõ. Không có báo cáo trước thì ghi "không có — lần quét đầu".

**Không** đưa vào prompt:
- nhận định của bạn về chỗ lệch;
- việc đã làm trong phiên;
- ghi chú của Thy (`$ARGUMENTS`);
- giả thuyết nào khác.

Agent phải tự tìm ra chỗ lệch. Đưa gợi ý vào thì kết quả chỉ xác nhận lại gợi ý, và công cụ hết độc lập.

## Bước 3 — Lưu báo cáo

1. **Kiểm header.** Dòng đầu báo cáo phải khớp khuôn
   `Promise gap: level <0-4> (<tên mức>) · coverage … · commit … (…) · YYYY-MM-DD`.
   - Không khớp thì gửi lại cho agent (SendMessage) để nó sửa đúng khuôn.
   - Không gửi được thì gọi lại agent, dùng cùng prompt và thêm yêu cầu đúng khuôn header.
   - Không tự sửa nội dung.
2. **Đặt tên file** `<here>/data/audits/promise-gap/<YYYY-MM-DD>-<NN>-<sha>.md`. `NN` (01, 02…) = **NN lớn nhất**
   cùng ngày ở mọi worktree (Bước 1.3) cộng 1. Không dùng "số file cộng 1": nếu số thứ tự đã bị hở thì sẽ ra tên trùng.
   Không ghi đè báo cáo cũ.
3. **Ghi nguyên văn** báo cáo vào file đó bằng Write.
   - Cần thêm ghi chú (ví dụ hai bản khác dòng lịch sử, hoặc một worktree bị chặn) thì đặt **một** khối
     `> Ghi chú của phiên chính: …` ngay dưới dòng header.
   - Không sửa phần nào của agent.

## Bước 4 — Báo lại cho Thy (ngắn)

Theo quy tắc CLAUDE.md: mọi thuật ngữ kỹ thuật có giải thích trong ngoặc ở lần đầu xuất hiện.

1. **Mức và xu hướng**: mức lệch (0–4, kèm tên mức; 4 là nặng nhất), độ phủ k/m, và so với lần trước: mức trước →
   sau, độ phủ trước → sau, số lời hứa đã khép / mới / nặng lên. Báo cáo trước có khối "Ghi chú của phiên chính" tính
   lại độ phủ thì lấy số đó làm mốc "trước", không lấy số ở dòng header.
2. **Ba gói việc đầu** theo thứ tự agent đề xuất. Mỗi gói ghi: khép được id nào, chi phí, vì sao đứng trước.
3. **Đường dẫn tuyệt đối** của file báo cáo.
4. **Ghi chú của Thy** (`$ARGUMENTS`), nếu có: đối chiếu với kết quả. Ví dụ Thy ghi đã làm X, agent có thấy X đã khép
   không.
5. **Điểm bạn không đồng ý** với agent (nếu có): nêu riêng, kèm bằng chứng `file:line`. Không lặng lẽ bỏ hay sửa kết
   luận của agent.

**Không** bắt tay sửa gì. Thy chọn gói việc rồi mới làm, theo quy trình nhánh, worktree, PR của `/git-flow`.
