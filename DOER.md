# Pepper Hunter DOER — đặc tả tầng TỰ LÀM (bản Actions, chốt 18:01 10/11/2026)

Hệ không chỉ tìm kèo + báo: **nó tự làm ra sản phẩm**. Ba tầng tách bạch:

| Tầng | Ai | Việc |
|---|---|---|
| Săn | Cloudflare Worker `pepper-hunter` (cron **mỗi phút**) | Quét GitHub bounty → cổng sạch → Gemini soạn work pack → Telegram; ghi vòng mới nhất vào KV `run:last`, đọc qua `GET /latest` |
| Thực thi | **GitHub Actions** — workflow `doer.yml` | Job vòng lặp tự nối ~330 phút, mỗi 60 giây chạy 1 vòng `doer.py` |
| Làm | **Gemini** (pool key account `donguyenthanhluan123@gmail.com`, repo secret `GEMINI_API_KEYS`, xoay 3.5 → 3.6 → 3.5-lite như Worker) | Soạn đơn xin việc + soạn sản phẩm thật |

> Thiết kế cũ "cron phía Muse chạy doer" đã BỎ. Muse chỉ còn vai trò kiểm tra/bảo trì hệ, không nằm trong vòng vận hành.

## Máy trạng thái (quan trọng nhất)

Nhiều kèo **phải thắng/được chọn trước mới được làm** (kiểu Synmerco thắng bid, sàn assignment kiểu Algora/Opire). Mỗi kèo có trường `mode`:

- **`lam_ngay`** — mở tự do, nộp trước thắng trước. Dấu hiệu: issue ghi "first PR", "no assignment needed", "just open a PR"... → làm sản phẩm ngay.
- **`cho_duoc_chon`** — phải được giao việc trước. Dấu hiệu: "comment to be assigned", "ask before working", "will assign", nhắc Algora/Opire, hoặc issue đã nhiều comment xin nhận. **Không rõ → mặc định `cho_duoc_chon`** (an toàn, tránh làm không công).

### Luồng `cho_duoc_chon`

1. **Nộp đơn** → trạng thái `applied`: Gemini sinh **comment xin nhận việc** (giới thiệu ngắn + kế hoạch + ETA; kèo chưa ghi ngân sách thì gộp luôn câu hỏi tiền bắt buộc) — lưu `deliverables/<slug>/APPLY.md`. Đây mới là *đơn ứng tuyển*, **chưa làm sản phẩm**. Gửi comment thật lên issue cần **PAT GitHub của Luân** (repo secret `GITHUB_PAT`): có PAT thì doer gửi ngay và ghi link comment; chưa có PAT thì đơn nằm sẵn trong repo, trạng thái ghi rõ "đã soạn, chờ PAT" — không giả vờ đã gửi.
2. **Chờ chọn**: mỗi vòng lặp kiểm tra lại issue — được assign cho `Luando-tester`, **hoặc** comment của chủ issue/bot sàn xác nhận giao việc, **hoặc** label `assigned`/`in-progress` → chuyển `assigned` + Telegram **"ĐƯỢC CHỌN"**.
3. **Làm**: chỉ khi `assigned` mới cho Gemini làm **sản phẩm đầy đủ** → `working`.
4. **Nộp**: có PAT → fork + branch + commit file sản phẩm vào `pepper-hunter-deliverable/` + mở PR (mặc định draft, `DOER_PR_DRAFT=0` để mở PR thường) → `submitted` + Telegram "đã nộp bài".
5. **Chờ trả**: PR merged → `cho_tra`. Tiền thực về ví chỉ ghi **`da_tra` khi có bằng chứng từ sàn/ví — không bao giờ suy đoán**.

### Luồng `lam_ngay`

`new` → làm sản phẩm ngay (`working`) → nộp ngay (`submitted`) → `cho_tra` → `da_tra` (theo bằng chứng).

### Trạng thái kết thúc khác

- `lost`: issue đã đóng, đã có người khác nhận, hoặc đơn chờ mà kèo vuột.
- `het_han`: đơn chờ quá `APPLIED_EXPIRE_DAYS` (mặc định 30 ngày).

## Sản phẩm theo loại kèo (`type`)

- `viet` (bài viết/research/docs/copy) → `deliverables/<slug>/SAN-PHAM.md`: bài/tài liệu **hoàn chỉnh** đúng yêu cầu issue; research chỉ dùng thông tin chắc chắn, số liệu/link chưa chắc ghi "cần kiểm chứng" — **không bịa số liệu**.
- `code` → `deliverables/<slug>/SOLUTION.md` (phân tích + cách làm + tiêu chí nghiệm thu) + các file code nháp Gemini sinh (tối đa 4 file).
- `khac` → `SAN-PHAM.md` dạng tài liệu/bản thảo theo yêu cầu.
- Kèo **chưa ghi ngân sách**: ở luồng `lam_ngay` vẫn làm (đã mở tự do) nhưng nếu thuộc `cho_duoc_chon` thì câu hỏi tiền nằm ngay trong đơn; không có mode nào được phép bịa số tiền.
- Mọi sản phẩm đều mang dòng ghi rõ: *"Bản thảo do Gemini làm — chưa nộp"*.

## Telegram — sự kiện riêng

Kèo mới · đã nộp đơn (gửi thật hoặc "đã soạn, chờ PAT") · **ĐƯỢC CHỌN** · đã nộp bài · tiền về (`da_tra`, chỉ khi có bằng chứng).

## Vận hành

- `state/doer_state.json` (trong repo): `{url: {title, slug, type, mode, status, budget_usd, files, applied_at, assigned_at, submitted_at, pr_url, ...}}` — doer commit sau mỗi vòng.
- `STATUS.md` (gốc repo): giờ chạy, số kèo từng trạng thái, hàng chờ được chọn, việc đã nộp — commit cùng state.
- Chống chạy trùng: `concurrency: pepper-hunter-doer`. Tự nối run: cuối job (còn ~150 giây) gọi `gh workflow run doer.yml` bằng `GITHUB_TOKEN` (permissions `actions: write` + `contents: write`).
- Thiếu secret nào doer **log rõ "chưa cấu hình"** và chạy ở chế độ suy giảm tương ứng (không Gemini → template offline; không PAT → chỉ soạn, không gửi/nộp; không Telegram → chỉ log) — không chết vòng lặp, không im lặng.

## Việc tay để mở khoá (Luân làm 1 lượt)

1. Duyệt quyền ghi cho Muse GitHub App trên repo `pepper-hunter-cron` (hoặc upload toàn bộ file qua web) — xem báo cáo của agent chính.
2. Đặt repo secrets: `GEMINI_API_KEYS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
3. Tạo PAT GitHub (tài khoản Luando-tester) → đặt secret `GITHUB_PAT` qua trang bảo mật — thiếu PAT thì hệ vẫn soạn đơn + sản phẩm nhưng không gửi comment/mở PR được.
4. Actions tab: bấm Run workflow `Pepper Hunter Doer` lần đầu để khởi động chuỗi tự nối.
