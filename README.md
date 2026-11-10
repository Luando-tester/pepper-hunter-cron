# Pepper Hunter Cron — săn kèo thật chạy không nghỉ, không cần mở laptop

Hệ săn kèo GitHub bounty THẬT, qua cổng sạch, soạn work pack bằng Gemini và báo
qua Telegram. Repo này là **public** có chủ đích: chỉ chứa code + work pack +
log tóm tắt, **không chứa bất kỳ key/token nào** (mọi bí mật nằm ở Secrets).

## Kiến trúc (bản mới — Cloudflare gánh phần định kỳ)

| Thành phần | Vai trò |
|---|---|
| **Cloudflare Worker** (`worker/worker.js`) | **RUNNER CHÍNH**: cron mỗi 30 phút tự quét GitHub bounty → lọc sạch → chống trùng bằng KV → Gemini soạn work pack → gửi Telegram. Chạy trên Cloudflare của Luân, laptop tắt vẫn chạy. |
| **GitHub repo này** | Kho chứa code, work pack (do lượt chạy tay sinh), và `state/seen.json` của bản Python. |
| **GitHub Actions** (`.github/workflows/hunter.yml`) | **Chỉ chạy tay** (workflow_dispatch) khi cần việc nặng: chạy `hunter.py` sinh work pack đầy đủ và commit vào repo. Không còn lịch cron — để tiết kiệm phút Actions. |
| **`hunter.py`** | Bản Python stdlib tương đương Worker, dùng để test local và cho lượt chạy tay trên Actions. |

Luồng mỗi vòng quét: GitHub Search API `label:bounty state:open` (ý định code /
AI agent / writing, tối đa 2 issue/repo, lọc PR) → trích ngân sách từ tiêu đề
(không ghi thì để "chưa ghi", **không bịa số**; "site credit" không tính là tiền)
→ cổng sạch loại kèo dính shill/spam/fake engagement/mule/laundering/gambling/
betting/captcha… → bỏ qua kèo đã thấy → Gemini (**pool tối đa 10 key xoay vòng**
giống tool local: mỗi key thử gemini-3.5-flash → 3.6-flash → 3.5-flash-lite;
429 hết quota thì đổi model/key kế, 400/401/403 thì bỏ key chết trong vòng chạy;
tất cả key đều fail thì lùi về template offline) soạn work pack; kèo chưa ghi
ngân sách thì pack bắt buộc có mẫu comment hỏi rõ tiền trước khi làm → gửi
Telegram kèm link + pack.

## Việc Luân phải làm tay 1 lần

### A. Tạo bot Telegram (để nhận thông báo)
1. Mở Telegram, tìm **@BotFather** → gửi `/newbot`.
2. Đặt tên hiển thị: `Pepper Hunter` → đặt username kết thúc bằng `bot`,
   ví dụ `pepper_hunter_luan_bot`.
3. BotFather trả về **token** dạng `123456789:AA...` — giữ kín, đừng gửi vào chat thường.
4. Mở bot vừa tạo, bấm **Start** (hoặc nhắn `hi`).
5. Lấy **chat_id**: mở trình duyệt vào
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   (thay `<TOKEN>` bằng token ở bước 3) → tìm `"chat":{"id":123456789,...}` —
   con số đó là `TELEGRAM_CHAT_ID`.

### B. Cấp key cho Cloudflare Worker (phần chính — agent sẽ điều phối deploy)
Khi Worker được deploy lên tài khoản Cloudflare của Luân, cần đặt secrets
cho Worker (qua dashboard Cloudflare hoặc `wrangler secret put`):

- **`GEMINI_API_KEYS`** — pool key Gemini, **tối đa 10 key** trong 1 giá trị:
  các key ngăn cách bằng **dấu phẩy** (`key1,key2,key3`) hoặc **mỗi key 1 dòng**.
  Hệ thống tự xoay vòng như tool local — 1 key hết quota/chết không làm nghẽn
  cả hệ, key kế tiếp gánh tiếp. **Muốn thêm key:** sửa lại secret này, dán thêm
  key vào cuối danh sách (vẫn ngăn cách dấu phẩy/xuống dòng, tối đa 10) rồi lưu —
  không cần sửa code. Cả 2 dạng key đều được: `AIza...` (đi header) và `AQ....`
  (đi query auth). *(Tương thích ngược: secret cũ `GEMINI_API_KEY` 1 key vẫn
  chạy — nó tự thành pool 1 key; có `GEMINI_API_KEYS` thì biến này được ưu tiên.)*
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

và tạo 1 KV namespace binding tên `SEEN` (chống trùng).
Trang chủ Worker (`GET /`) báo rõ số key đã cấu hình ở mục `gemini_keys`
(chỉ đếm số lượng, không in giá trị key).
**Việc deploy + tạo KV + gắn secrets do agent chính điều phối qua connector
Cloudflare Workers — Luân chỉ cần cung cấp token bot + chat_id + các Gemini key
qua kênh an toàn khi được hỏi, không dán vào repo.**

### C. (Tùy chọn) Cấp key cho lượt chạy tay trên GitHub Actions
Chỉ cần nếu muốn bấm chạy `hunter.py` trên Actions:
vào repo → **Settings → Secrets and variables → Actions → New repository secret**,
tạo các secret: `GEMINI_API_KEYS` (pool tối đa 10 key, ngăn cách dấu phẩy —
cách đặt giống mục B; hoặc `GEMINI_API_KEY` 1 key như cũ),
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Cách test

- **Worker** (sau khi deploy): mở `https://pepper-hunter.<subdomain>.workers.dev/`
  xem trạng thái cấu hình; mở thêm `/run` để chạy thử 1 vòng ngay, kết quả trả JSON.
- **Chạy tay trên Actions**: tab **Actions** → workflow **"Pepper Hunter (chay tay)"**
  → **Run workflow**. Xem log; pack mới và `state/seen.json` được commit tự động.
- **Local**: `python3 hunter.py` — thiếu biến môi trường nào nó log
  `chua cau hinh: ...` rõ ràng; thiếu cả 3 thì thoát êm mã 0.

## Lưu ý vận hành

- Cron của Cloudflare/GitHub đều có thể trễ vài phút so với lịch — bình thường.
- Worker free tier: 100.000 request/ngày — vòng 30 phút dùng rất ít, dư sức.
- Repo public lâu không hoạt động có thể bị GitHub tắt schedule của Actions —
  nhưng Actions ở đây không giữ lịch nữa nên không ảnh hưởng; phần định kỳ nằm
  ở Cloudflare Worker.
- Work pack do Gemini soạn là **bản chuẩn bị** (kế hoạch + khung deliverable +
  mẫu comment). Bước bid/nộp cuối trên sàn vẫn cần tài khoản của Luân.

## WATCHES — 7 watch kiếm tiền (từ 10/11/2026)

Theo lệnh của Luân, 7 watch kiếm tiền của PepperResearch (trước chạy bằng
cron agent Muse ở tab kiếm tiền) đã được port sang GitHub Actions TRONG
repo này — chung nhà với Worker Hunter + DOER, để không đốt token Muse
nữa. Code: `watches/watch.py`; workflow: `.github/workflows/watch.yml`
(vòng lặp tự nối ~330 phút, chu kỳ 60 giây/vòng, schedule */5 dự phòng —
pattern giống hệt DOER). Trạng thái sống từng watch: **`WATCHES.md`** ở
gốc repo; state dedupe bền: `state/watches_state.json`. Báo cáo ra cùng
group Telegram của hệ (secrets `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`
dùng chung).

| Watch | Nguồn | Hành vi | Điều kiện chạy thật |
|---|---|---|---|
| Synmerco | `synmerco-escrow.onrender.com` | Kèo sạch mới → **BID NGAY** theo luật giá 3 mức + lệch ngân sách (07/11); tự thêm capability khi 412; vòng lặp hạ giá theo đối thủ; báo thắng thầu | Secret `SYNMERCO_API_KEY` |
| CC0 storefront | KV `cc0-jobs` (Cloudflare) | Đọc index `meta:recent_job_ids` (bản vá KV-429), báo đơn PAID mới + probe + cảnh báo coverage. Chỉ đọc — fulfill/sweep là phase 2 (mở rộng Worker CC0) | Secret `CC0_CF_API_TOKEN` |
| MoltJobs | `api.moltjobs.io` | Stats trigger (public, luôn chạy) + heartbeat/assignment/job sạch; khung đêm 21:00–06:00 VN tự bid job đã kiểm chứng funded (ledger ≤10 bid free/tháng) | Secret `MOLTJOBS_API_KEY` |
| Owockibot | `bounty.owockibot.xyz` | Bounty sạch mới → **TỰ CLAIM** theo luật Luân duyệt 27/10 (chỉ cần địa chỉ ví MetaMask công khai — không cần credential) | Không cần secret |
| Fiverr | Gmail (mail thông báo seller) | **CHỜ-CONSENT**: bản gốc đọc qua Gmail — cần Luân consent Gmail OAuth 1 lần (giai đoạn 2), chưa port phần đọc mail | Gmail OAuth |
| Boards | Superteam / Taskmarket / HYRVE / Frantic | Kèo mới qua cổng sạch → báo; RaptorX đổi trạng thái/công bố winner → báo ngay | Không cần secret |
| Seller inbox | Gmail (Gumroad/Codester/Wirestock/Adobe/Upwork/Dreamstime) | **CHỜ-CONSENT** như Fiverr — không port phần đọc mail | Gmail OAuth |

Nguyên tắc chuyển giao (cứng, từ brief bàn giao tab kiếm tiền): cron Muse
ở tab kiếm tiền CHỈ tắt sau khi đường Actions tương ứng chạy thật và ra
đúng kết quả (việc chạm tiền phải chạy song song ≥3 lượt khớp + sự kiện
tiền thật đầu tiên qua đường mới có giám sát). Trong thời gian song song
chỉ một phía hành động ra ngoài cho mỗi nền tảng.
