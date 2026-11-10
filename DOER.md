# Pepper Hunter DOER — đặc tả tầng TỰ LÀM (bản Actions, chốt 18:01 10/11/2026)

Hệ không chỉ tìm kèo + báo: **nó tự làm ra sản phẩm**. Ba tầng tách bạch:

| Tầng | Ai | Việc |
|---|---|---|
| Săn | Cloudflare Worker `pepper-hunter` (cron **mỗi phút**) | Quét GitHub bounty → cổng sạch → Gemini soạn work pack → Telegram; ghi vòng mới nhất vào KV `run:last` + **hàng đợi tích lũy KV `queue`** (cap 100, dedupe theo url), đọc qua `GET /latest` |
| Thực thi | **GitHub Actions** — workflow `doer.yml` | Job vòng lặp tự nối ~330 phút, mỗi 60 giây chạy 1 vòng `doer.py` |
| Làm | **Gemini** (pool key account `donguyenthanhluan123@gmail.com`, repo secret `GEMINI_API_KEYS`, xoay 3.5 → 3.6 → 3.5-lite như Worker) | Soạn đơn xin việc + soạn sản phẩm thật |

> Thiết kế cũ "cron phía Muse chạy doer" đã BỎ. Muse chỉ còn vai trò kiểm tra/bảo trì hệ, không nằm trong vòng vận hành.

## Intake — 2 nguồn nạp kèo (vá lỗi 19:0x 10/11)

Bản đầu có 1 lỗi kép khiến doer chạy mà **không kèo nào lọt vào xử lý**: (1) nó chỉ đọc `GET /latest` — mà `/latest` chỉ giữ kèo của tick gần nhất, nên 9 kèo sạch đầu tiên (vòng 17:50) đã bị tick sau ghi đè trước khi doer khởi động; (2) Cloudflare chặn User-Agent mặc định `Python-urllib` (HTTP 403) và code cũ **return sớm ngay tại bước này**, bỏ qua toàn bộ vòng — kể cả ghi STATUS và commit, nên STATUS.md đứng yên như hệ chết. Đã vá:

1. **Intake 1 — Worker `/latest`**: doer đọc cả `deals` (tick gần nhất) lẫn `queue` (hàng đợi tích lũy của Worker), và luôn gửi User-Agent riêng `pepper-hunter-doer/1.0`. Lỗi `/latest` không còn giết vòng — intake 2 vẫn chạy.
2. **Intake 2 — doer tự quét GitHub Search**: mỗi vòng, doer tự chạy cùng bộ truy vấn của hunter (`label:bounty`, 3 ý định code/"AI agent"/writing, cap 2/repo), qua đúng cổng sạch (BANNED + bỏ qua "site credit"), và **đăng ký mọi kèo đang mở chưa có trong `state/doer_state.json`** — đây là đường bắt lại các kèo đã trôi (kèo còn mở trên sàn là bắt được; đã đóng/đã có assignee khác → ghi `lost` như logic sẵn có). Tổng đăng ký mới tối đa 12 kèo/vòng (`MAX_NEW_PER_CYCLE`) để bounded lượt gọi Gemini.

Sự kiện Telegram khi nạp kèo: **"NHAN KEO MOI VAO XU LY: \<title\> | mode: … | ngan sach: …"** ngay khi đăng ký, và **"BAT DAU XU LY: \<title\>"** khi bắt đầu sinh đơn/sản phẩm — mỗi sự kiện chỉ gửi 1 lần (cờ `notified_registered` / `notified_started` trong state, gửi thành công mới đặt cờ).

**Heartbeat STATUS**: `STATUS.md` luôn có dòng "Dang chay binh thuong - cap nhat HH:MM VN, tong keo dang theo doi: N, moi dang ky vong nay: M" và được commit lại **tối thiểu mỗi ~15 phút** (`DOER_HEARTBEAT_SEC`, mặc định 900) kể cả khi không có thay đổi — mở STATUS là biết hệ sống. (Vá kèm: `git push` phải dùng `HEAD:main` vì `actions/checkout` để repo ở detached HEAD — `git push` trần lỗi "not currently on a branch".)

## Máy trạng thái (quan trọng nhất)

Nhiều kèo **phải thắng/được chọn trước mới được làm** (kiểu Synmerco thắng bid, sàn assignment kiểu Algora/Opire). Mỗi kèo có trường `mode`:

- **`lam_ngay`** — mở tự do, nộp trước thắng trước. Dấu hiệu: issue ghi "first PR", "no assignment needed", "just open a PR"... → làm sản phẩm ngay.
- **`cho_duoc_chon`** — phải được giao việc trước. Dấu hiệu: "comment to be assigned", "ask before working", "will assign", nhắc Algora/Opire, hoặc issue đã nhiều comment xin nhận. **Không rõ → mặc định `cho_duoc_chon`** (an toàn, tránh làm không công).

### Luồng `cho_duoc_chon`

1. **Nộp đơn** → trạng thái `applied`: Gemini sinh **comment xin nhận việc** (giới thiệu ngắn + kế hoạch + ETA; kèo chưa ghi ngân sách thì gộp luôn câu hỏi tiền bắt buộc) — lưu `deliverables/<slug>/APPLY.md`. Đây mới là *đơn ứng tuyển*, **chưa làm sản phẩm**. Gửi comment thật lên issue cần **PAT GitHub của Luân** (repo secret `GH_PAT`, nạp vào env `GITHUB_PAT` — tên secret không được bắt đầu bằng `GITHUB_`). **PAT phải là classic, scope `public_repo`**: PAT fine-grained chỉ ghi được trong tài nguyên của chính chủ token — comment/PR lên repo người khác bị GitHub trả **403 "Resource not accessible by personal access token"** (đã kiểm chứng 10/11). Gặp 403, doer ghi `apply_blocked` kèm lý do vào state + STATUS và không thử lại liên tục. Có PAT hợp lệ thì doer gửi ngay và ghi link comment; chưa có thì đơn nằm sẵn trong repo, trạng thái ghi rõ "đã soạn, chờ PAT" — không giả vờ đã gửi. Đơn từng kẹt chưa gửi được sẽ **tự gửi bổ sung** (`resend_apply`, lấy thân comment từ APPLY.md) ở các vòng sau.
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

**NHAN KEO MOI VAO XU LY** (kèm mode + ngân sách, ngay khi đăng ký) · **BAT DAU XU LY** (khi bắt đầu sinh đơn/sản phẩm) · đã nộp đơn (gửi thật hoặc "đã soạn, chờ PAT") · **ĐƯỢC CHỌN** · đã nộp bài · tiền về (`da_tra`, chỉ khi có bằng chứng).

## Vận hành

- `state/doer_state.json` (trong repo): `{url: {title, slug, type, mode, status, budget_usd, files, applied_at, assigned_at, submitted_at, pr_url, ...}}` — doer commit sau mỗi vòng.
- `STATUS.md` (gốc repo): giờ chạy, số kèo từng trạng thái, hàng chờ được chọn, việc đã nộp — commit cùng state.
- Chống chạy trùng: `concurrency: pepper-hunter-doer`. Tự nối run: cuối job (còn ~150 giây) gọi `gh workflow run doer.yml` bằng `GITHUB_TOKEN` (permissions `actions: write` + `contents: write`).
- Thiếu secret nào doer **log rõ "chưa cấu hình"** và chạy ở chế độ suy giảm tương ứng (không Gemini → template offline; không PAT → chỉ soạn, không gửi/nộp; không Telegram → chỉ log) — không chết vòng lặp, không im lặng.

## Việc tay để mở khoá (Luân làm 1 lượt)

1. Duyệt quyền ghi cho Muse GitHub App trên repo `pepper-hunter-cron` (hoặc upload toàn bộ file qua web) — xem báo cáo của agent chính.
2. Đặt repo secrets: `GEMINI_API_KEYS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
3. Tạo **classic PAT** GitHub (tài khoản Luando-tester, scope `public_repo`) → đặt secret `GH_PAT` — thiếu PAT (hoặc dùng fine-grained) thì hệ vẫn soạn đơn + sản phẩm nhưng **không gửi comment/mở PR lên repo người khác được** (403). Bài học 10/11: 3 secrets `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`/`GH_PAT` từng bị đặt **rỗng giá trị** (API vẫn báo 201 và list vẫn hiện tên) khiến kênh Telegram + gửi đơn chết im lặng trong khi Gemini vẫn chạy — khi nghi ngờ, kiểm tra độ dài thật của env trong 1 workflow chẩn đoán, đừng tin danh sách tên secret. Secrets bị rỗng đã được đặt lại; các kèo đăng ký trong thời gian hỏng kênh được **backfill thông báo** bằng 1 tin tổng hợp "KENH THONG BAO DA SONG LAI" thay vì bắn lại từng sự kiện cũ.
4. Actions tab: bấm Run workflow `Pepper Hunter Doer` lần đầu để khởi động chuỗi tự nối.
