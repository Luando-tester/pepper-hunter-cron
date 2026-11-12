# Pepper Hunter DOER — đặc tả tầng TỰ LÀM (bản Actions, chốt 18:01 10/11/2026)

Hệ không chỉ tìm kèo + báo: **nó tự làm ra sản phẩm**. Ba tầng tách bạch:

| Tầng | Ai | Việc |
|---|---|---|
| Săn | Cloudflare Worker `pepper-hunter` (cron **mỗi phút**) | Quét GitHub bounty → cổng sạch → Gemini soạn work pack → Telegram; ghi vòng mới nhất vào KV `run:last` + **hàng đợi tích lũy KV `queue`** (cap 100, dedupe theo url), đọc qua `GET /latest`. **Ghi KV có điều kiện (11/11)**: KV free giới hạn ~1000 lần ghi/ngày mà ghi vô điều kiện 2 key/tick từng làm vỡ trần — nay `queue` chỉ ghi khi có kèo mới được thêm, `run:last` chỉ ghi khi có kèo sạch mới hoặc heartbeat ~15 tick/lần, đánh dấu seen chỉ khi có mục mới thật sự được xử lý; mỗi vòng đếm số lần ghi vào trường `kv_writes` |
| Thực thi | **GitHub Actions** — workflow `doer.yml` | Job vòng lặp tự nối ~330 phút, mỗi 60 giây chạy 1 vòng `doer.py` |
| Làm | **Gemini** (pool key account `donguyenthanhluan123@gmail.com`, repo secret `GEMINI_API_KEYS`, xoay 3.5 → 3.6 → 3.5-lite như Worker) | Soạn đơn xin việc + soạn sản phẩm thật |

> Thiết kế cũ "cron phía Muse chạy doer" đã BỎ. Muse chỉ còn vai trò kiểm tra/bảo trì hệ, không nằm trong vòng vận hành.

## Mô hình vận hành HIỆN TẠI (chốt 12/11/2026 — đọc mục này trước, các mục cũ bên dưới chỉ còn giá trị lịch sử)

Ba thay đổi lớn sau sự cố 11/11, theo thứ tự thời gian:

1. **HUNT-ONLY (18:59 11/11)** — kill-switch `state/control.json` ghi `{"outbound": false}` (file thiếu/hỏng → OFF, fail-closed): doer TUYỆT ĐỐI không gửi đơn/claim/follow-up/PR qua các đường cũ — `make_apply` / `resend_apply` / `submit_github` đều bị `outbound_guard()` chặn cứng, gửi đúng 0 request. Muốn mở lại outbound bắt buộc sửa control.json thành `{"outbound": true}` rồi commit (hành động có chủ đích). Telegram ở chế độ này chỉ nhận các loại tin: `choduyet`, `assigned` (ĐƯỢC GIAO KEO), `incident`, `tienve` (bật lại 05:21 12/11), `exec_done` (12/11); mọi tin routine bị gạt qua `notify()`.
2. **TU_XU — bỏ bước chờ duyệt (05:23 12/11)** — kèo mới qua kiểm chứng tiền thật KHÔNG còn đỗ chờ duyệt nữa: trạng thái đỗ cũ là `cho_duyet` (nay là di sản — entry nào còn ở đó tự chuyển sang `tu_xu` ở vòng kế tiếp, không báo trùng). Ở `tu_xu`, doer tự chuẩn bị nội bộ: soạn sẵn `deliverables/<slug>/APPLY.md` bằng **template an toàn** (chỉ hồ sơ thật REAL_PROFILE, KHÔNG dùng Gemini viết đơn tự do) + ghi `verify_note` (bằng chứng tín hiệu tiền thật) + báo đúng 1 tin loại `choduyet`, rồi theo dõi. Đơn soạn sẵn **không được gửi đi** (outbound vẫn khóa).
3. **EXECUTOR (07:56 12/11)** — kèo **ĐÃ ĐƯỢC GIAO** (trạng thái `assigned`: qua assignee/label/comment xác nhận của maintainer, hoặc maintainer comment **trao task cụ thể** trên kèo `tu_xu` — trigger 2, hàm `find_handover_comment`) thì doer **tự thực thi bằng Gemini như Muse**:
   - `deliverables/<slug>/TASK.md` = title + body issue + comment giao việc **NGUYÊN VĂN** — đó là phạm vi chốt: chỉ làm đúng yêu cầu ghi trong đó, không thêm bất kỳ yêu cầu nào; đặc tả thiếu/mơ hồ thì làm theo đọc hiểu đen tu (literal) và ghi giả định vào RESULT.md.
   - PLAN (Gemini) → PRODUCE trong sandbox tạm: kèo `code` thì clone repo đích (public, auth bằng classic PAT) rồi cài đặt đúng task; kèo `viet`/`khac` thì viết tài liệu trong workdir, chỉ dùng sự thật của REAL_PROFILE khi tự giới thiệu.
   - VERIFY bằng lệnh chuẩn của chính repo đích khi tìm thấy (package.json `scripts.test` → `npm test`; Makefile → `make test`; Python → `pytest`; không có thì fallback `py_compile`/`node --check`), vòng sửa lặp lại khi fail. **Trần cứng mỗi task: 60 lượt Gemini + ~25 phút.**
   - Artifacts chép vào `deliverables/<slug>/`: `TASK.md`, `RESULT.md` (việc đã làm + file + cách kiểm chứng + giả định), `files/<đường dẫn thật>` (kèo code) hoặc `SAN-PHAM.md` (kèo viết).
   - **Nộp bài qua hàm RIÊNG `submit_executor_result()`** — cổng riêng tách bạch với `outbound_guard` (outbound vẫn khóa cứng, xem mục 1): chỉ mở khi entry đúng `assigned` VÀ đã có sản phẩm executor (`exec_done_at` + `exec_result` + RESULT.md). Kèo code → mở **đúng 1 PR** từ fork/branch bằng classic PAT, body chỉ mô tả việc thật đã làm (file, kiểm chứng, kết quả — 0 nhận kinh nghiệm, có dòng định danh công cụ tự động của dự án cá nhân, qua LINT như mọi text ra ngoài). Kèo viet/khac → đăng **đúng 1 comment** chứa sản phẩm (khung qua LINT) kèm link file trong repo này. Nộp thành công → trạng thái `submitted`, vòng theo dõi merge/trả tiền sẵn có tiếp quản (`check_submitted` → `cho_tra` → `da_tra` → tin TIEN VE; riêng bài nộp bằng comment thì dấu hiệu nghiệm thu là issue được đóng sau khi giao).
   - Làm không xong / chạm trần / pool Gemini cạn → trạng thái **`exec_kẹt`** + đúng 1 tin `incident` (cạn key thì tin nói rõ hết key — **không bao giờ chết im lặng**) + giữ lại sản phẩm dở dang; executor **không tự chạy lại** (idempotent qua `exec_started_at`).
   - Cơ chế nộp không rõ hoặc nộp thất bại → trạng thái **`cho_nop_tay`** (sản phẩm đã xong, chờ nộp tay) + 1 tin `incident` — **không improvising kênh nộp khác**.
   - Muse (chat) chỉ còn nhận các mục cần chính Luân xử lý (KYC/ký ví/tạo tài khoản/dán key/liên kết tài khoản).
   - Cấm tuyệt đối như cũ: không đăng tuyển/ứng tuyển, không bịa claim hay task, kèo bẩn bị cổng sạch loại từ intake.

Các mục bên dưới (máy trạng thái `cho_duoc_chon`/`lam_ngay`, luồng nộp đơn bằng PAT, làm sản phẩm khi `assigned` bằng `make_product`...) mô tả **thiết kế gốc trước 11/11** — chỉ còn giá trị lịch sử và tham chiếu cho các cổng an toàn vẫn dùng chung (`presend_verify`, LINT, dedupe trước gửi, cổng repo bẫy/mirror, nhịp Telegram). Hành vi hiện hành lấy mục này + docstring đầu `doer.py` làm chuẩn.

## Intake — 2 nguồn nạp kèo (vá lỗi 19:0x 10/11)

Bản đầu có 1 lỗi kép khiến doer chạy mà **không kèo nào lọt vào xử lý**: (1) nó chỉ đọc `GET /latest` — mà `/latest` chỉ giữ kèo của tick gần nhất, nên 9 kèo sạch đầu tiên (vòng 17:50) đã bị tick sau ghi đè trước khi doer khởi động; (2) Cloudflare chặn User-Agent mặc định `Python-urllib` (HTTP 403) và code cũ **return sớm ngay tại bước này**, bỏ qua toàn bộ vòng — kể cả ghi STATUS và commit, nên STATUS.md đứng yên như hệ chết. Đã vá:

1. **Intake 1 — Worker `/latest`**: doer đọc cả `deals` (tick gần nhất) lẫn `queue` (hàng đợi tích lũy của Worker), và luôn gửi User-Agent riêng `pepper-hunter-doer/1.0`. Lỗi `/latest` không còn giết vòng — intake 2 vẫn chạy.
2. **Intake 2 — doer tự quét GitHub Search**: mỗi vòng, doer tự chạy **bộ truy vấn nới rộng đồng bộ cả 3 tầng** (11/11: 13 truy vấn — `label:bounty` × 3 ý định code/"AI agent"/writing + `label:bounty` trần + "bounty" trong tiêu đề không cần label + dấu hiệu tiền trong tiêu đề `"bounty $"`/`USDC` + `label:"help wanted"` × bounty/reward + nhắc nền tảng algora/opire + reward/"paid task"; **cap 3 issue/repo cho truy vấn tín hiệu cao** — label bounty/có tiền trong tiêu đề — **cap 2 cho còn lại**, 30 kết quả/truy vấn), qua đúng cổng sạch (BANNED + bỏ qua "site credit" + chặn repo bẫy), và **đăng ký mọi kèo đang mở chưa có trong `state/doer_state.json`** — đây là đường bắt lại các kèo đã trôi (kèo còn mở trên sàn là bắt được; đã đóng/đã có assignee khác → ghi `lost` như logic sẵn có). Tổng đăng ký mới tối đa 12 kèo/vòng (`MAX_NEW_PER_CYCLE`) để bounded lượt gọi Gemini. **Worker** dùng cùng bộ truy vấn nhưng **xoay vòng 4 tập theo tick** (mỗi phút 1 tập 3–4 truy vấn) vì gọi Search không auth (~10 req/phút theo IP dùng chung); dính rate-limit thì bỏ qua êm truy vấn đó, tick sau chạy tiếp.

Sự kiện Telegram khi nạp kèo: **"NHAN KEO MOI VAO XU LY: \<title\> | mode: … | ngan sach: …"** ngay khi đăng ký, và **"BAT DAU XU LY: \<title\>"** khi bắt đầu sinh đơn/sản phẩm — mỗi sự kiện chỉ gửi 1 lần (cờ `notified_registered` / `notified_started` trong state, gửi thành công mới đặt cờ).

## Cổng chặn repo bẫy bot (thêm 19:58 10/11)

Repo có **owner hoặc tên chứa `trap` / `honeypot` / `benchmark`** = bẫy dụ bot săn bounty (mẫu đã xác nhận: `PhanKhoa95/oss-bot-trap-benchmark` — 2 "kèo" $1.500/$1.600 không tiền thật). Luật áp **nhất quán ở cả 3 tầng** (`doer.py` + `hunter.py` + `worker/worker.js`): không đăng ký mới ở mọi intake; kèo đã lỡ nằm trong state thì doer tự chuyển **`skipped_trap`** kèm lý do hiện trong STATUS.md, không bao giờ gửi đơn, và báo Telegram "BO QUA KEO BAY BOT" 1 lần/kèo (cờ `trap_notified`, thử lại mỗi vòng tới khi gửi được). Chỉ xét owner/tên repo trong URL — không xét title/body để tránh bắt nhầm.

## Cổng kiểm chứng trước gửi + đơn chỉ dựa trên hồ sơ thật (vá khẩn 11/11 — sự cố SS14#44876)

**Sự cố**: lưới nới rộng vét trúng issue `space-wizards/space-station-14#44876` — đó là **báo lỗi cơ chế "bounty" TRONG GAME** (đặt gói hàng chứa bounty vào container khác thì ăn tiền thưởng game), không phải kèo trả tiền. Doer bản cũ gửi đơn Gemini soạn sẵn, trong đơn còn **bịa "strong experience in Space Station 14 codebase"** → bị cộng đồng cười ("grok is this real?"), agent cha phải xóa comment tay và dừng chuỗi. Hai lỗ hổng: (1) cổng sạch chỉ nhìn từ khoá/bẫy repo, không kiểm chứng **tín hiệu tiền thật**; (2) prompt soạn đơn không khóa nguồn giới thiệu nên Gemini tự bịa kinh nghiệm theo ngữ cảnh issue. Vá ở **doer** (chốt chặn cuối — Worker không bị đụng lượt này):

### 1. `presend_verify` — không có tín hiệu tiền thật thì không có gì rời hệ thống

Trước **mọi** đường gửi ra ngoài — `make_apply` (đơn mới), `resend_apply` qua nhánh `applied` (đơn gửi bổ sung), nâng nhánh `lam_ngay` trong `maybe_upgrade_mode`, nhánh `lam_ngay` cho kèo `new`, và `submit_github` (chốt chặn cuối trước khi fork/mở PR) — doer **fetch lại issue mới nhất** (`fetch_issue_info`: title + body + labels) và yêu cầu có **tín hiệu tiền thật** ở title/body/labels: mẫu `$ + số`, `số + USD/USDC/USDT`, nhắc nền tảng trả (**algora/opire**), hoặc **label bounty chính thức**. Chỉ khớp từ khoá "bounty" mà không có tín hiệu tiền → **CHẶN**: kèo chuyển trạng thái mới **`skipped_nopay`** (hiện trong STATUS.md kèm lý do), ghi `note` lý do (nếu labels có dấu hiệu ngữ cảnh game/bug-report kiểu `T: Bugfix`, `A: …` thì lý do ghi rõ "nghi 'bounty' là cơ chế ảo"), và báo Telegram **"BO QUA KEO - KHONG CO TIN HIEU TIEN THAT"** đúng 1 lần/kèo (cờ `nopay_notified`). Không đọc được issue để kiểm chứng cũng chặn (thà mất lượt còn hơn gửi mù). Nhờ gắn ở cả nhánh gửi bổ sung + `submit_github`, các kèo đã đăng ký từ trước khi có cổng này cũng bị chặn hồi tố.

### 2. Title aggregator rác — loại ngay từ intake

Title khớp mẫu `bounty alert | new paid opportunit… | new opportunities | opportunities today` (bài đăng lại kiểu "Bounty Alert: 14 New Opportunities…") bị bỏ qua ở **cả 2 intake** (`fetch_bounty_candidates` của intake 2 và `register_deal` dùng chung cho intake 1) — không đăng ký, không tốn lượt Gemini. `presend_verify` cũng kiểm lại mẫu này như lớp dự phòng.

### 3. Đơn chỉ được dựa trên HỒ SƠ THẬT + LINT chống bịa

- Khối **`REAL_PROFILE`** là nguồn giới thiệu **duy nhất** được phép dùng: *"PepperResearch — independent researcher/writer: cited research briefs and crypto/web3 research articles (published on dev.to), Python automation and Telegram bots (products listed on Gumroad and itch.io), data collection and research tasks. GitHub: Luando-tester."* `prompt_apply` (và đoạn tự giới thiệu trong `prompt_product`) nhúng nguyên khối này kèm lệnh cấm tuyệt đối: **không nhận kinh nghiệm với repo/project/codebase đích, khách hàng cũ, hay bất cứ thứ gì ngoài hồ sơ thật** — chỉ được liên hệ năng lực *chuyển đổi được* + kế hoạch cụ thể cho issue.
- **`lint_application`** chạy sau soạn, trước gửi (áp cho cả đơn mới lẫn thân đơn lấy lại từ APPLY.md khi gửi bổ sung): câu nhận kinh nghiệm bị bắt khi (1) chạm tên owner/repo/từ đặc trưng trong title của issue đích, hoặc (2) nhận kinh nghiệm với "codebase" (hồ sơ thật không có mục này), hoặc (3) không chứa bất kỳ năng lực nào của hồ sơ thật. Bắt được → **vứt draft, thay bằng `template_apply` an toàn** (chỉ hồ sơ thật dạng chung + kế hoạch + ETA + đoạn hỏi tiền nếu chưa ghi ngân sách), ghi `apply_lint_blocked` vào state. Harness đã chứng minh lint bắt đúng câu bịa của sự cố ("strong experience in Space Station 14 codebase logic") và không bắt nhầm đơn dựa trên hồ sơ thật.

### 4. Nhịp bắn Telegram

`telegram_send` (cả `doer.py` lẫn `watches/watch.py`): giãn tối thiểu **3,5 giây** giữa 2 tin liên tiếp (`TG_MIN_GAP_SEC`), gặp **429 thì tôn trọng `retry_after`** của Telegram, chờ rồi gửi lại tối đa 2 lần — vá sự cố bắn 12 tin cùng lúc bị rớt 4 tin.

## Xử lý trọn vòng — không kèo nào chết đứng (thêm 19:58 10/11)

- **Kèo chưa ghi ngân sách**: đơn luôn kèm đoạn hỏi tiền bắt buộc (`ASK_MONEY_EN`). Gemini quên chèn → code tự nối (`ensure_ask_money`); APPLY.md soạn từ các bản cũ thiếu đoạn hỏi → doer tự bổ sung vào file trước khi gửi (`ensure_apply_file_money`).
- **Thân comment gửi đi không còn placeholder**: mọi thân đơn (Gemini soạn, template, hay lấy lại từ APPLY.md khi gửi bổ sung) đều qua `sanitize_comment_body` — `[X] days` → `3 days`, `[X]` → `3`. Template offline ghi thẳng "My ETA is 3 days from assignment"; prompt Gemini cũng bắt buộc ghi số ngày cụ thể.
- **Fallback template rõ nhãn ở MỌI bước**: hết pool Gemini (429/403 project) → đơn dùng template, sản phẩm `viet`/`khac` dùng khung template, kèo `code` vẫn có `SOLUTION.md` template + `code-draft.md` ghi rõ "chưa sinh được — chờ Gemini phục hồi" (`product_incomplete`). `apply_mode`/`product_mode` trong state luôn ghi nguồn soạn (gemini key/model nào, hay template + lý do).
- Kèo `lam_ngay` được sinh sản phẩm ngay cả khi chưa ai giao; kèo `cho_duoc_chon` chỉ sinh sản phẩm sau khi `assigned` (đúng máy trạng thái ở dưới).

## Mượt mà — hết khựng (thêm 19:58 10/11)

- **Gửi lại đơn**: lỗi tạm thời → thử lại sau tối đa **30 phút** (`DOER_RESEND_BACKOFF_SEC`, thay cho 6 giờ cũ). Lỗi **403-do-token** → gắn cờ `awaiting_token` + vân tay PAT lúc bị chặn (`blocked_pat_fp` = sha256 rút gọn, không lưu giá trị token): không thử lại bằng token cũ; **ngay khi vân tay PAT thay đổi (đã thay classic PAT) thì tự mở cờ và gửi lại ở vòng kế tiếp**. Entry `apply_blocked` từ code cũ (chưa có vân tay) được thử gửi 1 lần để ghi vân tay mới.
- **Cách ly lỗi theo kèo**: xử lý từng kèo + từng điểm nạp intake đều bọc try/except riêng; lỗi được đếm vào dòng đầu STATUS.md ("loi da cach ly vong nay: N") và ghi `last_error` vào entry — 1 kèo văng lỗi không chết cả vòng, 1 vòng lỗi không giết job.
- **Chuỗi tự nối không phụ thuộc GH_PAT**: cuối job, doer tự dispatch run kế bằng **`GITHUB_TOKEN` của chính run** (env `GH_TOKEN`, permissions `actions: write`) — GH_PAT chỉ dùng cho comment/PR/sản phẩm. Dự phòng vẫn còn: schedule `*/5` trong `doer.yml` + concurrency group `pepper-hunter-doer`.

**Heartbeat STATUS**: `STATUS.md` luôn có dòng "Dang chay binh thuong - cap nhat HH:MM VN, tong keo dang theo doi: N, moi dang ky vong nay: M" và được commit lại **tối thiểu mỗi ~15 phút** (`DOER_HEARTBEAT_SEC`, mặc định 900) kể cả khi không có thay đổi — mở STATUS là biết hệ sống. (Vá kèm: `git push` phải dùng `HEAD:main` vì `actions/checkout` để repo ở detached HEAD — `git push` trần lỗi "not currently on a branch".)

## Máy trạng thái (quan trọng nhất)

> **LƯU Ý 12/11:** mục này mô tả thiết kế GỐC. Hiện hành: kèo chờ được chọn đỗ ở `tu_xu` (đơn soạn sẵn bằng template an toàn, KHÔNG gửi — mục "Mô hình vận hành HIỆN TẠI" ở đầu tài liệu), và kèo được giao đi **EXECUTOR** tự làm + nộp bài, không qua luồng `make_product`/`submit_github` bên dưới (hai đường đó đang bị outbound_guard khóa cứng).

Nhiều kèo **phải thắng/được chọn trước mới được làm** (kiểu Synmerco thắng bid, sàn assignment kiểu Algora/Opire). Mỗi kèo có trường `mode`:

> **LUẬT MODE CHỐT CUỐI (Luân chốt 07:06–07:07 11/11 — "tùy kèo mà xử")**: nền là các kèo thua đều thua trước đối thủ nộp PR/sản phẩm sẵn, nhưng KHÔNG vì thế mà tự làm trước khi chưa được mời. Chỉ 3 nhánh:

- **`lam_ngay`** — CHỈ khi issue **nói rõ mời làm ngay**: "first PR", "first come", "no assignment needed", "no need to be assigned", "just open a PR", "open a PR directly", "go ahead"... → làm sản phẩm ngay + mở PR nháp ngay trong cùng vòng, và các kèo này được **ưu tiên xử lý đầu vòng**.
- **`cho_duoc_chon`** — issue **cấm làm trước**: "comment to be assigned", "ask before working", "will assign", nhắc Algora/Opire, hoặc issue đã nhiều comment xin nhận.
- **`cho_duoc_chon` (mặc định)** — issue **IM LẶNG** (không mời làm ngay, không cấm): **im lặng = chờ-được-chọn, kể cả kèo code có ngân sách rõ** — không tự làm trước.

Mỗi kèo ghi trường **`mode_reason`** trong state (và hiện trong STATUS.md ở các dòng new/applied/assigned/working) để đối chiếu vì sao kèo đi nhánh đó. **Phân loại lại MỖI VÒNG** cho kèo đang `applied` (`maybe_upgrade_mode`): tín hiệu mới nhất thắng — comment của maintainer mới hơn mô tả issue (mô tả ghi "first PR" nhưng maintainer vừa comment "ask before working" thì phải chờ); maintainer comment "go ahead" → tự nâng lên `lam_ngay`, làm sản phẩm + mở PR nháp ngay; ngược lại vẫn im lặng thì giữ chờ. Kèo đã ở `lam_ngay` không tự hạ nhánh. Kèo gốc `applied` được nâng lên làm sản phẩm vẫn **canh thua bình thường** ở trạng thái `working` (issue đóng / người khác được giao → `lost` + báo Telegram).

### Luồng `cho_duoc_chon`

1. **Nộp đơn** → trạng thái `applied`: Gemini sinh **comment xin nhận việc** (giới thiệu ngắn + kế hoạch + ETA; kèo chưa ghi ngân sách thì gộp luôn câu hỏi tiền bắt buộc) — lưu `deliverables/<slug>/APPLY.md`. Đây mới là *đơn ứng tuyển*, **chưa làm sản phẩm**. Gửi comment thật lên issue cần **PAT GitHub của Luân** (repo secret `GH_PAT`, nạp vào env `GITHUB_PAT` — tên secret không được bắt đầu bằng `GITHUB_`). **PAT phải là classic, scope `public_repo`**: PAT fine-grained chỉ ghi được trong tài nguyên của chính chủ token — comment/PR lên repo người khác bị GitHub trả **403 "Resource not accessible by personal access token"** (đã kiểm chứng 10/11). Gặp 403, doer ghi `apply_blocked` kèm lý do vào state + STATUS và không thử lại liên tục. Có PAT hợp lệ thì doer gửi ngay và ghi link comment; chưa có thì đơn nằm sẵn trong repo, trạng thái ghi rõ "đã soạn, chờ PAT" — không giả vờ đã gửi. Đơn từng kẹt chưa gửi được sẽ **tự gửi bổ sung** (`resend_apply`, lấy thân comment từ APPLY.md) ở các vòng sau.
2. **Chờ chọn**: mỗi vòng lặp kiểm tra lại issue — được assign cho `Luando-tester`, **hoặc** comment của chủ issue/bot sàn xác nhận giao việc, **hoặc** label `assigned`/`in-progress` → chuyển `assigned` + Telegram **"ĐƯỢC CHỌN"**.
3. **Làm**: chỉ khi `assigned` mới cho Gemini làm **sản phẩm đầy đủ** → `working`.
4. **Nộp**: có PAT → fork + branch + commit file sản phẩm vào `pepper-hunter-deliverable/` + mở PR (mặc định draft, `DOER_PR_DRAFT=0` để mở PR thường) → `submitted` + Telegram "đã nộp bài".
5. **Chờ trả**: PR merged → `cho_tra`. Tiền thực về ví chỉ ghi **`da_tra` khi có bằng chứng từ sàn/ví — không bao giờ suy đoán**.

### Luồng `lam_ngay`

`new` → làm sản phẩm ngay (`working`) → **mở PR nháp ngay trong cùng vòng** (`submitted`) → `cho_tra` → `da_tra` (theo bằng chứng). Kèo `applied` được nâng nhánh lên cũng đi tiếp đúng luồng này từ trạng thái `working`.

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

**Thông báo kết thúc đơn chờ (thêm 11/11):**

- **"KEO VE NGUOI KHAC (thua)"** — bắn đúng 1 lần ở vòng chuyển sang `lost`, kèm tiêu đề + link + lý do (`check_assignment` trả kèm lý do: "issue da dong" hoặc "da giao cho @user..."). Trước đây nhánh này chỉ ghi status/note, không có Telegram.
- **"DON HET HAN CHO (30 ngay khong phan hoi)"** — bắn đúng 1 lần ở vòng chuyển sang `het_han` (chờ quá `APPLIED_EXPIRE_DAYS`).
- **"DON DANG NGAM"** — tin **tổng hợp**, mỗi ngày tối đa 1 tin: liệt kê các đơn `applied` đã chờ **≥ 3 ngày** chưa có phản hồi (tiêu đề + số ngày chờ + link, tối đa 15 đơn, sắp xếp chờ lâu nhất trước). Chỉ gửi khi có ít nhất 1 đơn đạt ngưỡng; mốc ngày đã gửi lưu ở `state/doer_meta.json` (`soak_report_date`, giờ VN UTC+7) để không bắn trùng trong ngày — không bắn từng đơn lẻ.

## Vận hành

- `state/doer_state.json` (trong repo): `{url: {title, slug, type, mode, mode_reason, status, budget_usd, files, applied_at, assigned_at, submitted_at, pr_url, ...}}` — doer commit sau mỗi vòng.
- `state/doer_meta.json` (trong repo): mốc phụ trợ ngoài state kèo — hiện dùng cho `soak_report_date` (ngày đã gửi tin tổng hợp "đơn đang ngâm"), commit cùng state.
- `STATUS.md` (gốc repo): giờ chạy, số kèo từng trạng thái, hàng chờ được chọn, việc đã nộp — commit cùng state.
- Chống chạy trùng: `concurrency: pepper-hunter-doer`. Tự nối run: cuối job (còn ~150 giây) gọi `gh workflow run doer.yml` bằng `GITHUB_TOKEN` (permissions `actions: write` + `contents: write`).
- Thiếu secret nào doer **log rõ "chưa cấu hình"** và chạy ở chế độ suy giảm tương ứng (không Gemini → template offline; không PAT → chỉ soạn, không gửi/nộp; không Telegram → chỉ log) — không chết vòng lặp, không im lặng.

## Việc tay để mở khoá (Luân làm 1 lượt)

1. Duyệt quyền ghi cho Muse GitHub App trên repo `pepper-hunter-cron` (hoặc upload toàn bộ file qua web) — xem báo cáo của agent chính.
2. Đặt repo secrets: `GEMINI_API_KEYS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
3. ~~Tạo **classic PAT** GitHub (scope `public_repo`) → đặt secret `GH_PAT`~~ — **ĐÃ XONG 20:11 10/11**: classic PAT scope `public_repo` đã nằm trong secret `GH_PAT` (lượt đầu Luân quên tick scope → 403 "Must have admin rights", sửa scope tại chỗ trên token, giá trị không đổi). Kiểm chứng: đơn kèo tari#3489 đã gửi thật bằng token này (comment 6768221502, state đã ghi `apply_sent=true` để doer không gửi trùng). Mọi run doer **bắt đầu sau 20:11 10/11** đều mang token classic → 12 đơn `applied` còn chờ sẽ tự gửi bổ sung nhờ cơ chế vân tay PAT ở mục "Mượt mà". Thiếu PAT (hoặc dùng fine-grained) thì hệ vẫn soạn đơn + sản phẩm nhưng **không gửi comment/mở PR lên repo người khác được** (403). Bài học 10/11: 3 secrets `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`/`GH_PAT` từng bị đặt **rỗng giá trị** (API vẫn báo 201 và list vẫn hiện tên) khiến kênh Telegram + gửi đơn chết im lặng trong khi Gemini vẫn chạy — khi nghi ngờ, kiểm tra độ dài thật của env trong 1 workflow chẩn đoán, đừng tin danh sách tên secret. Secrets bị rỗng đã được đặt lại; các kèo đăng ký trong thời gian hỏng kênh được **backfill thông báo** bằng 1 tin tổng hợp "KENH THONG BAO DA SONG LAI" thay vì bắn lại từng sự kiện cũ.
4. Actions tab: bấm Run workflow `Pepper Hunter Doer` lần đầu để khởi động chuỗi tự nối.

## WATCHES (hệ anh em — từ 10/11/2026)

Repo này còn chứa hệ WATCHES: `watches/watch.py` + workflow `watch.yml`
(7 watch kiếm tiền port từ cron Muse của tab kiếm tiền: Synmerco, CC0,
MoltJobs, Owockibot, Fiverr, Boards, Seller inbox — xem bảng đầy đủ ở
README.md). Mặt tiền trạng thái là `WATCHES.md` (gốc repo), state ở
`state/watches_state.json` — tách bạch với `STATUS.md`/`doer_state.json`
của DOER, hai hệ commit các file khác nhau nên không giẫm nhau (watch có
thêm rebase-retry khi push). DOER chỉ làm việc trên GitHub; WATCHES lo
phần còn lại của mảng kiếm tiền. Fiverr + Seller inbox đang chờ consent
Gmail OAuth; CC0 fulfill/sweep thuộc phase 2 (Worker CC0 tự fulfill).
