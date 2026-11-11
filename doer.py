#!/usr/bin/env python3
"""Pepper Hunter DOER - tang TU LAM chay bang GitHub Actions (workflow doer.yml).

Worker Cloudflare chi SAN keo (GET /latest). Doer la thang THUC THI:
doc keo sach moi -> phan loai (type + mode) -> lam san pham bang Gemini
(pool key, secret GEMINI_API_KEYS) -> gui Telegram -> ghi state + STATUS.md
-> commit vao repo. Job vong lap tu noi: moi 60s 1 vong, toi da ~330 phut,
gan het gio thi tu workflow_dispatch chay run moi (gh CLI + GITHUB_TOKEN).

INTAKE 2 NGUON: (1) Worker /latest (deals tick gan nhat + queue tich luy);
(2) doer TU QUET GitHub Search cung bo truy van voi hunter - bat lai keo da
troi khoi /latest (ban dau /latest chi giu 1 vong nen 9 keo dau tien bi ghi
de truoc khi doer khoi dong). Dang ky moi -> Telegram "NHAN KEO MOI VAO XU
LY"; bat dau sinh don/san pham -> "BAT DAU XU LY" (moi su kien 1 lan, co co
trong state). STATUS.md co dong heartbeat va duoc commit lai toi thieu moi
~15 phut (DOER_HEARTBEAT_SEC) ke ca khi khong co thay doi.

NANG CAP 19:58 10/11: (a) CONG BAY BOT - repo owner/ten chua "trap"/
"honeypot"/"benchmark" thi khong dang ky, keo da co -> skipped_trap;
(b) xu ly TRON VONG moi keo: don cua keo chua ghi ngan sach luon co doan
hoi tien (ke ca APPLY.md soan tu truoc - ensure_apply_file_money), than
comment gui di duoc sanitize het placeholder [X] (ETA mac dinh 3 ngay);
(c) MUOT: loi 403-do-token gan co awaiting_token theo van tay PAT (chi gui
lai khi token thay), loi tam thoi backoff toi da 30 phut; loi tung keo/tung
diem nap duoc cach ly + dem vao STATUS, loi toan vong khong giet job.

VA KHAN 11/11 (su co SS14#44876 - don bia kinh nghiem vao issue loi game):
(1) CONG KIEM CHUNG TRUOC GUI: moi duong gui ra ngoai (don moi, don gui bo
sung, nang nhanh lam_ngay, mo PR) deu fetch lai issue va bat buoc co TIN
HIEU TIEN THAT (title/body/labels: $+so, USD/USDC/USDT, algora/opire, label
bounty) - khong co thi chan, chuyen skipped_nopay + bao Telegram 1 lan;
title aggregator rac bi bo qua ngay tu intake. (2) DON CHI DUA TREN HO SO
THAT (REAL_PROFILE): prompt cam bia kinh nghiem, them LINT sau soan bat cau
nhan kinh nghiem voi repo/project dich hoac ngoai ho so -> thay bang
template an toan. (3) Telegram gian nhip >= 3.5s/tin + retry theo
retry_after khi 429.

VA HE THONG 11/11 CHIEM (su co IES-BoilerRoom/cuda-warp-allreduce-verifier#1:
7 comment don trung + bia "experienced in CUDA kernel optimization" tren 1
issue mirror gia danh escrow): (1) LINT NGHIEM v2 - bo trigger nhan kinh
nghiem morphology-safe (bat ca "experienced/skilled/background in...") +
denylist ky nang ngoai ho so; moi duong gui ra (don moi, gui bo sung, than
PR) deu qua gate_outbound_text(): co cau bia la THAY TOAN BO bang template
an toan. Ban cu thoat vi CLAIM_RE khong nhan bien the "experienced" va cau
chen tu khoa ho so that thi qua cong. (2) DEDUPE TRUOC GUI: ngay truoc POST
comment, GET lai comment cua issue - da co comment cua Luando-tester thi
danh dau apply_sent, khong gui nua (doc lap voi state: cuu truong hop run
truoc gui that nhung bi huy truoc khi commit state). (3) LOC MIRROR o
intake: body khop mau "Conformance Mirror"/"not reviewed on this mirror"/
"Specification Shards"/regression-runner, hoac repo < 30 ngay tuoi ma moi
issue deu la bai escrow/conformance -> skipped_trap ngay tu dang ky, cong
kiem chung truoc gui cung chan. (4) SINGLE-FLIGHT: self_dispatch kiem tra
run doer.yml dang active truoc khi dispatch (cong sau: concurrency group
trong doer.yml).

MAY TRANG THAI (luan chot 18:01 10/11 - nhieu keo phai THANG/DUOC CHON truoc):
  mode=lam_ngay      : CHI khi issue NOI RO moi lam ngay (OPEN_SIGNALS:
                       "first pr", "no assignment needed", "just open a pr",
                       "go ahead"...) -> lam san pham ngay + mo PR nhap ngay,
                       duoc UU TIEN xu ly dau vong.
  mode=cho_duoc_chon : issue cam lam truoc (ASSIGN_SIGNALS) HOAC issue IM LANG
                       (khong moi, khong cam) -> MAC DINH CHO, ke ca keo code
                       co ngan sach ro (im lang = cho, khong tu lam truoc):
      new -> applied (sinh APPLY.md = don xin nhan viec; gui comment that
             bang GITHUB_PAT neu co, chua co PAT thi don nam san trong repo)
          -> assigned (issue duoc assign cho minh / chu xac nhan / label)
          -> working (luc nay moi lam san pham) -> submitted -> cho_tra
          -> da_tra (CHI khi co bang chung tien ve - doer khong tu suy doan)
      applied ma issue dong / co nguoi khac nhan -> lost; cho qua lau -> het_han
      (ca hai deu bao Telegram 1 lan o vong chuyen trang thai; don applied
      cho >= 3 ngay chua phan hoi -> moi ngay 1 tin tong hop "don dang ngam")
  Phan loai lai MOI VONG cho keo applied: tin hieu moi xuat hien (sua mo ta /
  comment maintainer "go ahead"...) -> tu doi nhanh theo tin hieu moi nhat;
  moi keo ghi mode_reason ly do di nhanh do.

Bien moi truong:
  WORKER_URL          mac dinh https://pepper-hunter.pepperresearch.workers.dev
  GEMINI_API_KEYS     pool toi da 10 key (phay/xuong dong); GEMINI_API_KEY = pool 1
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   bao Telegram (thieu -> bo qua, chi log)
  GITHUB_PAT          PAT cua Luando-tester: gui comment xin viec, fork + mo PR.
                      Thieu PAT: doer van soan don/san pham, trang thai dung o
                      applied/working kem ghi chu "cho PAT", KHONG gia vo da gui.
  GH_TOKEN/GITHUB_TOKEN  cho lenh gh tu dispatch run moi o cuoi job.
  OUR_USERNAME        mac dinh Luando-tester (tai khoan duoc assign).
  DOER_LOOP_BUDGET_MIN=330  DOER_POLL_SEC=60  DOER_ONCE=1 (chay 1 vong roi thoat)
  DOER_GIT=1/0        commit+push (tu bat khi GITHUB_ACTIONS=true)
  DOER_DISPATCH=1/0   tu noi run moi (tu bat khi GITHUB_ACTIONS=true)
  DOER_PR_DRAFT=1     mo PR dang draft (mac dinh 1; =0 de mo PR thuong)
  APPLIED_EXPIRE_DAYS=30  don cho qua so ngay nay -> het_han
Chi dung thu vien chuan. Loi tung nguon chi log, khong giet vong lap.
"""
import hashlib, json, os, re, subprocess, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "state", "doer_state.json")
META_PATH = os.path.join(BASE_DIR, "state", "doer_meta.json")
SOAK_MIN_DAYS = 3
STATUS_PATH = os.path.join(BASE_DIR, "STATUS.md")
DELIV_DIR = os.path.join(BASE_DIR, "deliverables")

WORKER_URL = (os.environ.get("WORKER_URL") or "https://pepper-hunter.pepperresearch.workers.dev").rstrip("/")
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
MAX_GEMINI_KEYS = 10
OUR_USERNAME = os.environ.get("OUR_USERNAME") or "Luando-tester"
LOOP_BUDGET_MIN = float(os.environ.get("DOER_LOOP_BUDGET_MIN") or 330)
POLL_SEC = int(os.environ.get("DOER_POLL_SEC") or 60)
APPLIED_EXPIRE_DAYS = int(os.environ.get("APPLIED_EXPIRE_DAYS") or 30)
HEARTBEAT_SEC = int(os.environ.get("DOER_HEARTBEAT_SEC") or 900)
RESEND_BACKOFF_SEC = int(os.environ.get("DOER_RESEND_BACKOFF_SEC") or 1800)

# --- Intake 2: doer TU QUET GitHub Search (cung bo truy van + cong sach voi
# hunter.py / worker.js). Day la duong bat lai keo da troi khoi /latest
# (Worker chi giu vong gan nhat; keo con mo tren san la bat lai duoc).
# LUOI NOI RONG (11/11): bo truy van dong bo ca 3 tang (doer.py + hunter.py +
# worker.js). Moi truy van la (query, hi): hi=True = tin hieu cao (label bounty
# / co tien trong tieu de) -> cap 3 issue/repo; hi=False -> cap 2 issue/repo.
# Doer auth bang classic PAT (30 req/phut) nen chay TRON BO 13 truy van moi
# vong nap; Worker khong auth nen xoay vong theo tap.
SEARCH_QUERIES = [
    ("is:issue is:open label:bounty code", True),
    ('is:issue is:open label:bounty "AI agent"', True),
    ("is:issue is:open label:bounty writing", True),
    ("is:issue is:open label:bounty", True),
    ("is:issue is:open bounty in:title", True),
    ('is:issue is:open "bounty $" in:title', True),
    ("is:issue is:open USDC bounty", True),
    ('is:issue is:open label:"help wanted" bounty', False),
    ('is:issue is:open label:"help wanted" reward', False),
    ("is:issue is:open algora bounty", False),
    ("is:issue is:open opire bounty", False),
    ("is:issue is:open reward bounty in:title", False),
    ('is:issue is:open "paid task" bounty', False),
]
MAX_PER_REPO = 2
MAX_PER_REPO_HI = 3
SEARCH_PER_PAGE = 30
MAX_NEW_PER_CYCLE = 12
BANNED = [
    "shill", "spam", "fake engagement", "fake follower", "fake review",
    "money mule", "mule account", "laundering", "gambling", "betting",
    "casino", "captcha farm", "captcha solving", "airdrop farm",
    "pump and dump", "paid retweet farm",
    "generate gmv", "qualifying gmv", "fake volume", "wash trading", "wash trade",
    "simulated volume", "bot traffic", "fake traffic",
]

# --- Cong chan REPO BAY BOT (chot 19:58 10/11): repo co owner/ten chua cac dau
# hieu nay la bay du bot san bounty tu dong (vd PhanKhoa95/oss-bot-trap-benchmark
# chua 2 "keo" $1.500/$1.600 khong tien that) -> KHONG dang ky moi, keo da co
# trong state chuyen skipped_trap, khong bao gio gui don. Ap dung nhat quan o
# doer.py + hunter.py + worker/worker.js.
TRAP_MARKERS = ["trap", "honeypot", "benchmark"]


def trap_repo_reason(url):
    """Tra ly do bay neu URL issue thuoc repo bay bot, None neu sach.
    Chi nhin owner/repo trong URL - khong dung title/body (tranh bat nham)."""
    p = parse_issue_url(url)
    if not p:
        return None
    owner, repo = p[0], p[1]
    low = (owner + "/" + repo).lower()
    for m in TRAP_MARKERS:
        if m in low:
            return ("repo %s/%s chua dau hieu bay bot ('%s') - bo qua, khong dang ky, "
                    "khong gui don" % (owner, repo, m))
    return None

# --- Bo loc MIRROR / BAY O TANG BODY + TUOI REPO (bo sung sau su co
# IES-BoilerRoom/cuda-warp-allreduce-verifier#1): cac repo "Automated CI
# Conformance Mirror" gia danh escrow ($450 USDC + ten cac rail algora/polar/
# opire trong body) nen CO tin hieu tien gia -> cong kiem chung theo tin hieu
# tien khong bat duoc. Dau hieu nhan dien nam o KHUNG MO TA (mirror notice,
# "not reviewed on this mirror", "Specification Shards", regression runner)
# hoac o HINH DANG REPO: repo moi tao < 30 ngay ma toan bo issue deu la bai
# escrow/conformance.
MIRROR_BODY_RES = [
    re.compile(r"conformance mirror", re.I),
    re.compile(r"not reviewed on this mirror", re.I),
    re.compile(r"manual pull requests?[^.\n]{0,80}not reviewed", re.I),
    re.compile(r"specification shards", re.I),
    re.compile(r"\bregression runner\b", re.I),
    re.compile(r"automated ci\b[^.\n]{0,60}(mirror|regression)", re.I),
]
ESCROW_TITLE_RE = re.compile(r"escrow|conformance", re.I)
REPO_AGE_TRAP_DAYS = 30
_REPO_AGE_CACHE = {}


def mirror_body_reason(title, body):
    """Tra ly do mirror/bay neu title/body khop mau mirror, None neu sach."""
    text = (title or "") + "\n" + (body or "")
    for r in MIRROR_BODY_RES:
        m = r.search(text)
        if m:
            return "body khop mau mirror/bay bot: '%s'" % m.group(0)[:70]
    return None


def repo_age_trap_reason(url):
    """Repo tao chua du REPO_AGE_TRAP_DAYS ngay ma MOI issue cua no deu la
    bai escrow/conformance -> bay mirror kieu IES-BoilerRoom. Ket qua cache
    theo repo trong phien chay de khong goi API lap lai moi ung vien."""
    p = parse_issue_url(url)
    if not p:
        return None
    key = "%s/%s" % (p[0], p[1])
    if key in _REPO_AGE_CACHE:
        return _REPO_AGE_CACHE[key]
    reason = None
    try:
        st, repo = gh_api("GET", "/repos/%s/%s" % (p[0], p[1]))
        if st == 200 and isinstance(repo, dict):
            created = datetime.fromisoformat((repo.get("created_at") or "").replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created).days
            if age_days < REPO_AGE_TRAP_DAYS:
                st2, issues = gh_api("GET", "/repos/%s/%s/issues?state=all&per_page=50" % (p[0], p[1]))
                if st2 == 200 and isinstance(issues, list):
                    titles = [(i.get("title") or "") for i in issues
                              if isinstance(i, dict) and "pull_request" not in i]
                    if titles and all(ESCROW_TITLE_RE.search(t) for t in titles):
                        reason = ("repo %s moi tao %d ngay, ca %d issue deu la bai "
                                  "escrow/conformance - bay mirror, bo qua"
                                  % (key, age_days, len(titles)))
    except Exception:
        reason = None
    _REPO_AGE_CACHE[key] = reason
    return reason


# --- Cong KIEM CHUNG TRUOC GUI (va khan 11/11, sau su co SS14#44876): don
# xin viec / PR khong duoc roi he thong neu issue khong co TIN HIEU TIEN
# THAT. Su co: luoi noi rong vet trung issue bao loi co che "bounty" TRONG
# GAME (khong he co tien that), doer cu gui don bia kinh nghiem -> cong dong
# cuoi, agent cha phai xoa comment tay. Day la chot chan CUOI o doer - moi
# duong gui ra ngoai (make_apply, resend_apply, nhanh lam_ngay, submit_github)
# deu phai qua cong nay.
AGGREGATOR_TITLE_RE = re.compile(
    r"bounty alert|new paid opportunit|new opportunities|opportunities today", re.I)
MONEY_SIGNAL_RES = [
    re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?"),
    re.compile(r"\d[\d,]*(?:\.\d+)?\s?(?:USDC|USDT|USD)\b", re.I),
    re.compile(r"\b(?:algora|opire)\b", re.I),
]


def has_money_signal(title, body, labels):
    """Tin hieu tien THAT trong title/body/labels: $ + so, so + USD/USDC/USDT,
    nhac nen tang tra bounty (algora/opire), hoac label bounty chinh thuc."""
    text = (title or "") + "\n" + (body or "")
    if any(r.search(text) for r in MONEY_SIGNAL_RES):
        return True
    return any("bounty" in (l or "").lower() for l in (labels or []))


def game_context_hints(labels):
    """Nhan co dau hieu ngu canh ao/game (taxonomy kieu SS14: 'T: Bugfix',
    'A: Cargo/Salvage'...). Chi de ghi ly do chan cho ro rang - dieu kien chan
    chinh van la VANG tin hieu tien that."""
    hints = []
    for l in labels or []:
        ll = (l or "").lower()
        if "bugfix" in ll or ll.startswith("a:"):
            hints.append(l)
    return hints


def presend_verify(entry, info):
    """KIEM CHUNG TRUOC KHI GUI don/PR. info phai la fetch_issue_info MOI
    NHAT (title + body + labels). Tra (ok, ly_do_chan)."""
    if info is None:
        return False, "khong doc duoc issue de kiem chung truoc khi gui"
    title = info.get("title") or entry.get("title") or ""
    body = info.get("body") or ""
    labels = info.get("labels") or []
    if AGGREGATOR_TITLE_RE.search(title or ""):
        return False, "title dang aggregator rac - bo qua"
    mr = mirror_body_reason(title, body)
    if mr:
        return False, "issue thuoc mirror/bay bot - " + mr
    if has_money_signal(title, body, labels):
        return True, ""
    hints = game_context_hints(labels)
    if hints:
        return False, ("khong co tin hieu tien that + label ngu canh game/bug report (%s) "
                       "- nghi 'bounty' o day la co che ao, khong phai keo tra tien"
                       % ", ".join(hints))
    return False, "khong co tin hieu tien that (chi khop tu khoa 'bounty')"


def block_presend(entry, reason):
    """Chuyen 1 keo bi cong kiem chung chan sang skipped_nopay + bao Telegram
    1 lan. Chi dung khi CHUA co gi duoc gui ra ngoai cho keo nay.
    Rieng ly do MIRROR/bay -> skipped_trap (dung ban chat hon skipped_nopay)."""
    if "mirror" in reason:
        entry["status"] = "skipped_trap"
        entry["trap_notified"] = True  # tin ben duoi da la thong bao duy nhat
    else:
        entry["status"] = "skipped_nopay"
    entry["note"] = "kiem chung truoc gui chan: " + reason
    log("CHAN GUI (kiem chung truoc gui) %s: %s" % (entry["url"], reason))
    if not entry.get("nopay_notified"):
        if telegram_send("[Pepper Hunter Doer] BO QUA KEO - KHONG CO TIN HIEU TIEN THAT\n%s\nLink: %s\nLy do: %s"
                         % (entry["title"], entry["url"], reason)):
            entry["nopay_notified"] = True


IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"
DOER_ONCE = os.environ.get("DOER_ONCE") == "1"
DOER_GIT = os.environ.get("DOER_GIT", "1" if IN_ACTIONS else "0") == "1"
DOER_DISPATCH = os.environ.get("DOER_DISPATCH", "1" if IN_ACTIONS else "0") == "1"
PR_DRAFT = os.environ.get("DOER_PR_DRAFT", "1") != "0"

ASK_MONEY_EN = ("Before I begin, could you please confirm: 1) the exact bounty amount, "
                "2) how it is paid (for example USDC to a wallet, or through this platform) "
                "and when (after PR merge / after approval), and 3) the acceptance criteria "
                "for a successful submission? Thank you!")
NOTE_DRAFT = "<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->\n\n"

ASSIGN_SIGNALS = [
    "comment to be assigned", "to be assigned", "ask before working",
    "ask before you start", "ask first", "will assign", "assignment required",
    "get assigned", "before working on", "please comment before",
    "comment to claim", "comment before working", "algora", "opire",
]
OPEN_SIGNALS = [
    "first pr", "first come", "first-come", "no assignment needed",
    "no need to be assigned", "no assignment", "just open a pr",
    "open a pr directly", "feel free to open a pr", "submit a pr directly",
    "go ahead",
]
ASSIGN_CONFIRM_WORDS = ["assigned", "go ahead", "all yours", "please proceed",
                        "you're on it", "you are on it", "feel free to start",
                        "looking forward to your pr"]
VIET_WORDS = ["write", "writing", "article", "blog", "content", "documentation",
              "docs", "readme", "tutorial", "guide", "research", "copywriting",
              "translate", "translation", "essay", "newsletter", "post"]
CODE_WORDS = ["fix", "bug", "implement", "feature", "refactor", "api", "sdk",
              "library", "function", "test", "ci", "performance", "code",
              "develop", "script", "bot", "integration", "add support",
              "endpoint", "cli", "parser"]


def log(msg):
    print("[DOER %s] %s" % (datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_key_pool():
    raw = (os.environ.get("GEMINI_API_KEYS") or "").strip()
    parts = []
    if raw:
        parts = [p.strip() for p in re.split(r"[,\n]", raw) if p.strip()]
    else:
        single = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if single:
            parts = [single]
    pool, seen = [], set()
    for k in parts:
        if k in seen:
            continue
        seen.add(k)
        pool.append(k)
        if len(pool) >= MAX_GEMINI_KEYS:
            break
    return pool


def http_req(method, url, headers=None, data=None, timeout=60):
    req = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def http_json(method, url, headers=None, obj=None, timeout=60):
    data = json.dumps(obj).encode() if obj is not None else None
    h = dict(headers or {})
    if obj is not None:
        h["Content-Type"] = "application/json"
    st, raw = http_req(method, url, h, data, timeout)
    try:
        return st, json.loads(raw)
    except Exception:
        return st, {"raw": raw[:400]}


# --- Nhip ban Telegram: toi thieu TG_MIN_GAP_SEC giua 2 tin lien tiep
# (su co 11/11: ban 12 tin cung luc bi Telegram 429 rot mat 4 tin); gap 429
# thi ton trong retry_after cua Telegram, cho roi gui lai toi da 2 lan.
TG_MIN_GAP_SEC = float(os.environ.get("TG_MIN_GAP_SEC") or 3.5)
_TG_LAST_SEND = [0.0]


def _tg_wait_turn():
    wait = _TG_LAST_SEND[0] + TG_MIN_GAP_SEC - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _TG_LAST_SEND[0] = time.monotonic()


def _tg_post_once(token, chat, text):
    body = urllib.parse.urlencode({"chat_id": chat, "text": text[:3900],
                                   "disable_web_page_preview": "true"}).encode()
    st, raw = http_req("POST", "https://api.telegram.org/bot%s/sendMessage" % token,
                       {"Content-Type": "application/x-www-form-urlencoded"}, body, 30)
    ok, retry_after = False, None
    try:
        d = json.loads(raw)
        ok = bool(d.get("ok"))
        if not ok:
            retry_after = (d.get("parameters") or {}).get("retry_after")
    except Exception:
        pass
    return ok, st, raw, retry_after


def telegram_send(text):
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chats = []
    for _k in ("TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID_2"):
        _c = (os.environ.get(_k) or "").strip()
        if _c and _c not in chats:
            chats.append(_c)
    if not token or not chats:
        return False
    ok_main = False
    for _i, chat in enumerate(chats):
        ok, st, raw = False, None, ""
        for attempt in range(3):
            _tg_wait_turn()
            ok, st, raw, retry_after = _tg_post_once(token, chat, text)
            if ok:
                break
            if st == 429 or retry_after:
                delay = max(float(retry_after or 5), TG_MIN_GAP_SEC)
                log("Telegram 429 (chat %d, lan gui %d) - cho %.0fs roi gui lai"
                    % (_i + 1, attempt + 1, delay))
                time.sleep(delay)
            else:
                break
        if _i == 0:
            ok_main = ok
        if not ok:
            log("Telegram loi (HTTP %s): %s" % (st, str(raw)[:160]))
    return ok_main


def pat_fingerprint():
    """Van tay rut gon cua GITHUB_PAT hien tai (sha256, 12 ky tu hex dau) -
    chi de PHAT HIEN token da duoc thay (fine-grained -> classic) ma khong
    luu gia tri token. Rong neu chua co PAT."""
    pat = (os.environ.get("GITHUB_PAT") or "").strip()
    if not pat:
        return ""
    return hashlib.sha256(pat.encode()).hexdigest()[:12]


def gh_headers():
    h = {"User-Agent": "pepper-hunter-doer/1.0", "Accept": "application/vnd.github+json"}
    pat = (os.environ.get("GITHUB_PAT") or "").strip()
    if pat:
        h["Authorization"] = "Bearer " + pat
    return h


def gh_api(method, path, obj=None):
    return http_json(method, "https://api.github.com" + path, gh_headers(), obj, 60)


def parse_issue_url(url):
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", url or "")
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


def make_slug(url, title=""):
    p = parse_issue_url(url)
    if p:
        raw = "%s-%s-%s" % p
    else:
        raw = re.sub(r"[^a-z0-9]+", "-", (title or "deal").lower()).strip("-")[:60] or "deal"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-")[:80]


def fetch_issue_info(url):
    """Lay thong tin issue tu GitHub API (co PAT thi dung PAT, khong thi an danh).
    Tra dict {state, assignees, labels, comments, body, title} hoac None."""
    p = parse_issue_url(url)
    if not p:
        return None
    st, d = gh_api("GET", "/repos/%s/%s/issues/%d" % p)
    if st != 200 or not isinstance(d, dict):
        log("Khong doc duoc issue %s (HTTP %s)" % (url, st))
        return None
    return {
        "state": d.get("state"),
        "assignees": [a.get("login") for a in (d.get("assignees") or [])],
        "labels": [l.get("name", "") for l in (d.get("labels") or [])],
        "comments": d.get("comments", 0),
        "body": (d.get("body") or "")[:6000],
        "title": d.get("title") or "",
    }


def fetch_issue_comments(url):
    p = parse_issue_url(url)
    if not p:
        return []
    st, d = gh_api("GET", "/repos/%s/%s/issues/%d/comments?per_page=100" % p)
    if st != 200 or not isinstance(d, list):
        return []
    return [{"user": (c.get("user") or {}).get("login", ""),
             "association": c.get("author_association", ""),
             "id": c.get("id"),
             "html_url": c.get("html_url", ""),
             "body": (c.get("body") or "")[:1500]} for c in d]


def already_commented(url):
    """KIEM TRA TRUNG LAP NGAY TRUOC KHI GUI: Luando-tester da co comment
    tren issue nay chua? Day la chot chan doc lap voi state - cuu cac truong
    hop run truoc da gui that nhung bi huy truoc khi commit state (state mat
    co apply_sent -> run sau gui lai; su co IES: 7 comment trung tren 1
    issue). Tra (da_co, html_url_cua_comment). Loi doc API -> (False, '')
    de khong chan oan (van con cong kiem chung + lint phia truoc)."""
    try:
        for c in fetch_issue_comments(url):
            if (c.get("user") or "") == OUR_USERNAME:
                return True, c.get("html_url", "")
    except Exception:
        pass
    return False, ""


# ---------------------------------------------------------------- Cong sach + Intake 2
def extract_budget(title):
    """Trich ngan sach tu title (giong hunter.py). Khong co -> None. Cam bia so."""
    if "credit" in (title or "").lower():
        return None
    m = re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)", title or "")
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s?(USDC|USDT|USD)\b", title or "", re.I)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def clean_gate(text):
    low = (text or "").lower()
    return [w for w in BANNED if w in low]


def is_site_credit(text):
    return "site credit" in (text or "").lower()


def fetch_bounty_candidates():
    """Intake 2: tu quet GitHub Search (bo noi rong 13 truy van, cap 3/repo
    cho truy van tin hieu cao, 2/repo cho con lai), qua cong sach + bo qua
    site credit. Tra list {title, url, budget_usd, pack}
    (pack = excerpt cua issue). Loi tung truy van chi log."""
    items, seen_url, per_repo = [], set(), {}
    for q, hi in SEARCH_QUERIES:
        cap = MAX_PER_REPO_HI if hi else MAX_PER_REPO
        path = ("/search/issues?q=%s&sort=created&order=desc&per_page=%d"
                % (urllib.parse.quote(q), SEARCH_PER_PAGE))
        st, data = gh_api("GET", path)
        if st != 200 or not isinstance(data, dict):
            # PAT fine-grained co the khong doc duoc search -> thu an danh
            st2, raw = http_req("GET", "https://api.github.com" + path,
                                {"User-Agent": "pepper-hunter-doer/1.0",
                                 "Accept": "application/vnd.github+json"}, None, 40)
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
            if st2 != 200 or not isinstance(data, dict):
                log("Intake2: GitHub search '%s' loi (HTTP %s/%s) - bo qua truy van nay" % (q, st, st2))
                continue
        for it in data.get("items", []):
            if "pull_request" in it:
                continue
            html = it.get("html_url", "")
            if not html or html in seen_url:
                continue
            title = (it.get("title") or "").strip()
            if len(title) < 6:
                continue
            if AGGREGATOR_TITLE_RE.search(title):
                log("Intake2 BO QUA bai aggregator rac: %s" % title[:70])
                continue
            repo = ""
            ru = it.get("repository_url", "")
            if "/repos/" in ru:
                repo = ru.split("/repos/", 1)[1]
            if per_repo.get(repo, 0) >= cap:
                continue
            if trap_repo_reason(html):
                log("Intake2 BO QUA repo bay bot (%s): %s" % (repo, title[:70]))
                continue
            excerpt = re.sub(r"\s+", " ", it.get("body") or "")[:600]
            if mirror_body_reason(title, excerpt):
                log("Intake2 BO QUA mirror/bay o body (%s): %s" % (repo, title[:70]))
                continue
            text = title + " " + excerpt
            hits = clean_gate(text)
            if hits:
                log("Intake2 LOAI BAN (%s): %s" % (", ".join(hits), title[:70]))
                continue
            if is_site_credit(text):
                log("Intake2 bo qua site credit: %s" % title[:70])
                continue
            per_repo[repo] = per_repo.get(repo, 0) + 1
            seen_url.add(html)
            items.append({"title": title, "url": html,
                          "budget_usd": extract_budget(title), "pack": excerpt})
        log("Intake2 query '%s': tich luy %d ung vien sach" % (q, len(items)))
    return items


def notify_started(entry):
    """Su kien Telegram: BAT DAU XU LY (gui 1 lan duy nhat, co co trong state)."""
    if entry.get("notified_started"):
        return
    if telegram_send("[Pepper Hunter Doer] BAT DAU XU LY: %s\nLink: %s"
                     % (entry["title"], entry["url"])):
        entry["notified_started"] = True


def register_deal(state, deal):
    """Dang ky 1 keo (tu /latest hoac intake tu quet) vao state. Tra entry neu
    dang ky moi, None neu da co. Gui Telegram su kien NHAN KEO ngay khi nhan."""
    url = deal.get("url")
    if not url or url in state:
        return None
    if AGGREGATOR_TITLE_RE.search(deal.get("title") or ""):
        log("Khong dang ky bai aggregator rac: %s" % (deal.get("title") or "")[:70])
        return None
    trap = trap_repo_reason(url) or mirror_body_reason(deal.get("title"), deal.get("pack"))
    info = fetch_issue_info(url)
    if not trap and info:
        trap = (mirror_body_reason(info.get("title"), info.get("body"))
                or repo_age_trap_reason(url))
    slug = make_slug(url, deal.get("title", ""))
    entry = {"title": deal.get("title", ""), "url": url, "slug": slug,
             "budget_usd": deal.get("budget_usd"), "pack": (deal.get("pack") or "")[:6000],
             "status": "new", "created_at": now_iso(), "updated_at": now_iso(), "files": []}
    if trap:
        # Ghi nhan skipped_trap vao state (thay vi bo qua am tham) de khong
        # quet/gui lai o cac vong sau + co thong bao 1 lan qua vong migration.
        entry["status"] = "skipped_trap"
        entry["note"] = trap
        entry["type"] = classify_type(entry["title"], entry["pack"])
        entry["mode"] = "cho_duoc_chon"
        state[url] = entry
        log("Dang ky skipped_trap (khong gui don): %s (%s)" % (url, trap))
        return entry
    if info and info.get("state") == "closed":
        entry["status"] = "lost"
        entry["note"] = "issue da dong truoc khi kip lam"
    elif info and (info.get("assignees") or []):
        if OUR_USERNAME in info["assignees"]:
            entry["mode"] = "cho_duoc_chon"
            entry["type"] = classify_type(entry["title"], entry["pack"])
            entry["status"] = "assigned"
            entry["note"] = "da duoc assign san cho " + OUR_USERNAME
        else:
            entry["status"] = "lost"
            entry["note"] = "da co nguoi nhan: " + ", ".join(info["assignees"])
    else:
        entry["type"] = classify_type(entry["title"], entry["pack"])
        entry["mode"], entry["mode_reason"] = classify_mode(entry["title"], entry["pack"], info)
    state[url] = entry
    if entry["status"] in ("new", "assigned"):
        budget_txt = ("$" + str(entry["budget_usd"])) if entry.get("budget_usd") else "chua ghi"
        if telegram_send("[Pepper Hunter Doer] NHAN KEO MOI VAO XU LY: %s | mode: %s | ngan sach: %s\nLink: %s"
                         % (entry["title"], entry.get("mode", "?"), budget_txt, url)):
            entry["notified_registered"] = True
        log("Da dang ky keo (%s/%s/%s): %s"
            % (entry["status"], entry.get("mode", "?"), entry.get("type", "?"), entry["title"][:70]))
    return entry


# ---------------------------------------------------------------- Gemini pool
def gemini_call_once(key, model, prompt):
    url = ("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model)
    headers = {"Content-Type": "application/json"}
    if str(key).startswith("AQ"):
        url += "?key=" + urllib.parse.quote(key, safe="")
    else:
        headers["x-goog-api-key"] = key
    st, d = http_json("POST", url, headers,
                      {"contents": [{"parts": [{"text": prompt}]}]}, 300)
    if st != 200:
        detail = ""
        if isinstance(d, dict):
            detail = str((d.get("error") or {}).get("message") or "")[:160]
        return "", st, detail
    try:
        parts = d["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts), 200, ""
    except Exception:
        return "", 200, "response khong co text"


def gemini_generate_pool(pool, pool_state, prompt):
    """Xoay pool giong worker.js: 429 -> model ke cung key; 404 -> bo model cho
    key do trong ca phien; 400/401/403 -> key chet trong ca phien."""
    last_err = ""
    for ki, key in enumerate(pool):
        if ki in pool_state["dead"]:
            continue
        gone = pool_state["gone"].setdefault(ki, set())
        for model in GEMINI_MODELS:
            if model in gone:
                continue
            text, st, detail = gemini_call_once(key, model, prompt)
            if text:
                log("Gemini OK: key #%d model %s" % (ki + 1, model))
                return text, "gemini (key #%d, %s)" % (ki + 1, model)
            last_err = "key #%d %s HTTP %s %s" % (ki + 1, model, st, detail)
            log("Gemini " + last_err)
            if st in (400, 401, 403):
                pool_state["dead"].add(ki)
                log("Gemini key #%d chet (HTTP %s) -> bo trong phien nay" % (ki + 1, st))
                break
            if st == 404:
                gone.add(model)
                continue
            if st == 429:
                continue
    return "", "template (tat ca key Gemini deu fail: %s)" % last_err


# ---------------------------------------------------------------- Phan loai
def classify_type(title, text):
    low = ((title or "") + " " + (text or "")).lower()
    v = sum(1 for w in VIET_WORDS if w in low)
    c = sum(1 for w in CODE_WORDS if w in low)
    if v > c:
        return "viet"
    if c > 0:
        return "code"
    return "khac"


def detect_signals(low_text):
    """Quet 2 bo phrase tren van ban da lower-case. Tra (assign_hit, open_hit)
    - moi gia tri la phrase dau tien khop hoac None. Thu tu uu tien khi dung:
    ASSIGN (cam lam truoc) thang OPEN (moi lam ngay) vi an toan."""
    a = next((s for s in ASSIGN_SIGNALS if s in low_text), None)
    o = next((s for s in OPEN_SIGNALS if s in low_text), None)
    return a, o


def classify_mode(title, text, info):
    """LUAT MODE (chot cuoi 07:07 11/11 - 'tuy keo ma xu'):
    - issue NOI RO moi lam ngay (OPEN_SIGNALS) -> lam_ngay.
    - issue cam lam truoc (ASSIGN_SIGNALS) -> cho_duoc_chon.
    - issue IM LANG (khong moi, khong cam) -> cho_duoc_chon MAC DINH, ke ca
      keo code co ngan sach ro (im lang = cho, khong tu lam truoc).
    Tra (mode, mode_reason)."""
    low = ((title or "") + " " + (text or "")).lower()
    a, o = detect_signals(low)
    if a:
        return "cho_duoc_chon", "issue cam lam truoc: '%s' -> cho duoc chon" % a
    if o:
        return "lam_ngay", "issue noi ro moi lam ngay: '%s' -> lam san pham + mo PR nhap ngay" % o
    if info and (info.get("comments") or 0) >= 5:
        return "cho_duoc_chon", "issue da co nhieu comment (%d) - nghi nhieu nguoi xin nhan -> cho duoc chon" % info["comments"]
    return "cho_duoc_chon", "issue im lang (khong moi lam ngay, khong cam) -> mac dinh cho duoc chon"


# ---------------------------------------------------------------- Prompt + template
def deal_context(deal, info):
    body = (info or {}).get("body") or deal.get("pack") or ""
    return ("Keo: %s\nLink: %s\nNgan sach: %s\n\nNoi dung issue / work pack:\n%s"
            % (deal["title"], deal["url"],
               ("$" + str(deal["budget_usd"])) if deal.get("budget_usd") else "CHUA GHI",
               body[:5000]))


# --- HO SO THAT: nguon DUY NHAT duoc phep dua vao don xin viec / doan tu
# gioi thieu trong san pham. Luan chot sau su co SS14: "khong duoc bia, dua
# tren du lieu that" - don chi duoc nhan cac nang luc duoi day + lien he
# CHUYEN DOI duoc sang keo nay + ke hoach cu the. CAM TUYET DOI: nhan kinh
# nghiem voi repo/project/codebase dich, khach hang cu, hay bat ky thu gi
# ngoai ho so nay. Co them LINT sau soan chan don bia truoc khi gui.
REAL_PROFILE = ("PepperResearch - independent researcher/writer: cited research briefs and "
                "crypto/web3 research articles (published on dev.to), Python automation and "
                "Telegram bots (products listed on Gumroad and itch.io), data collection and "
                "research tasks. GitHub: Luando-tester.")
REAL_CLAIM_KEYS = ["research", "dev.to", "python", "telegram", "gumroad", "itch.io",
                   "itch", "data collection", "automation", "writing", "writer",
                   "brief", "github", "crypto", "web3"]
GENERIC_TITLE_WORDS = {"bounty", "issue", "feature", "request", "improve", "support",
                       "update", "adds", "adding", "using", "about", "there",
                       "their", "which", "would", "could"}


def target_tokens(deal):
    """Tu khoa dinh danh issue dich (owner/repo tach thanh tung tu + tu dac
    trung dai >= 5 ky tu trong title). Don nhan kinh nghiem cham vao cac tu
    nay = bia kinh nghiem voi dich."""
    toks = set()
    p = parse_issue_url(deal.get("url") or "")
    if p:
        toks.add(p[0].lower())
        toks.add(p[1].lower())
        toks.add(p[1].lower().replace("-", " ").replace("_", " "))
        for w in re.split(r"[-_/]", p[1].lower()):
            if len(w) >= 4:
                toks.add(w)
    for w in re.findall(r"[a-z0-9]{5,}", (deal.get("title") or "").lower()):
        if w not in GENERIC_TITLE_WORDS:
            toks.add(w)
    return toks


CLAIM_RE = re.compile(r"[^.\n]*\b(experience|expertise|expert in|worked on|speciali[sz]\w*|proficient|familiar with)\b[^.\n]*", re.I)

# --- LINT NGHIEM v2 (thay CO CHE, khong chi them cum tu - bai hoc su co IES
# 11/11): ban lint cu hong o 3 cho: (1) CLAIM_RE chi nhan dang dung cac tu
# "experience/expertise/..." o dang nguyen the - bien the "experienced" thoat
# vi \b sau nhom khong khop khi con chu cai theo sau; (2) cau nhan kinh
# nghiem thoat neu trong cau co chen 1 tu khoa ho so that bat ky (vd vua nhan
# "Python" vua nhan CUDA trong cung 1 cau thi qua); (3) chi quet cac cau co
# dung tu khoa nhan kinh nghiem trong danh sach hep - cac dang "skilled in",
# "strong background in", "I have built...", "8+ years" khong bi quet.
# Co che moi: (a) bo kich hoat (trigger) MORPHOLOGY-SAFE (goc tu + \w*) va
# bao phu moi dang tu nhan nang luc o ngu canh don xin viec; (b) bat ky cau
# nao da kich hoat deu bi coi la BIA neu chua tu khoa cam (denylist ky
# nang/ky thuat ngoai ho so), cham dinh danh dich, co "codebase", co mau
# "X years", HOAC khong chua nang luc ho so that nao - tuc la cau nhan kinh
# nghiem chi SACH khi no dua HOAN TOAN tren ho so that; (c) moi duong gui ra
# deu qua gate_outbound_text(): co van de la THAY TOAN BO text bang template
# an toan, khong bao gio gui text goc.
CLAIM_TRIGGER_RE = re.compile(
    r"experienc\w*|expert\w*|speciali[sz]\w*|proficien\w*|familiar\w*|"
    r"skill\w*|background in|knowledge of|worked (on|with|at)|"
    r"(i|we|i've|we've) (have )?(built|developed|created|written|designed|shipped|delivered)\b|"
    r"my (work|background|expertise|track record)|track record|"
    r"\d+\s*\+?\s*years?|years? of|hands-on|well-versed|adept|seasoned|"
    r"deep (understanding|knowledge)|strong (grasp|understanding)",
    re.I)
# Ky nang/ky thuat NGOAI ho so that - xuat hien trong cau nhan kinh nghiem
# la bia, bat ke cau co chen tu khoa ho so that hay khong.
FORBIDDEN_CLAIM_TOKENS = [
    "cuda", "gpu", "kernel", "fp8", "fp16", "bf16", "sm90", "hopper",
    "tensor core", "rust", "solidity", "c++", "c#", "golang", "java",
    "typescript", "javascript", "react", "kubernetes", "docker",
    "machine learning", "deep learning", "smart contract", "embedded",
    "firmware", "fpga", "verilog", "devops", "backend", "front-end",
    "frontend", "full-stack", "fullstack", "android", "ios",
    "game development", "unity", "unreal", "blockchain development",
    "data engineering", "cloud architecture", "aws", "azure", "gcp",
]
YEARS_RE = re.compile(r"\d+\s*\+?\s*years?\b|years? of (experience|work)", re.I)


def _claim_segments(text):
    """Cat text thanh cac doan cau (theo dau cham/xuong dong/cham phay) -
    don vi de quet nhan kinh nghiem."""
    segs = []
    for part in re.split(r"[.\n;]+", text or ""):
        seg = part.strip(" -\t")
        if len(seg) >= 12:
            segs.append(seg)
    return segs


def lint_application(text, deal):
    """LINT sau soan / truoc gui (v2): bat cau nhan kinh nghiem BIA. 1 doan
    cau bi coi la nhan kinh nghiem khi khop CLAIM_TRIGGER_RE (moi dang tu
    nhan nang luc, ke ca bien the nhu 'experienced'); doan do la BIA khi:
    (1) chua ky nang/ky thuat ngoai ho so (FORBIDDEN_CLAIM_TOKENS); hoac
    (2) cham dinh danh owner/repo/title cua issue dich; hoac
    (3) nhan kinh nghiem voi 'codebase' (ho so that khong co muc nay); hoac
    (4) co mau so nam kinh nghiem ('5+ years'...); hoac
    (5) khong dua tren bat ky nang luc nao cua ho so that (REAL_CLAIM_KEYS).
    Cau nhan kinh nghiem CHI sach khi dua hoan toan tren ho so that.
    Tra list cac doan bi bat (rong = sach, duoc gui)."""
    problems = []
    targets = target_tokens(deal)
    for seg in _claim_segments(text):
        if not CLAIM_TRIGGER_RE.search(seg):
            continue
        low = seg.lower()
        if any(tok in low for tok in FORBIDDEN_CLAIM_TOKENS):
            problems.append(seg)
        elif any(t and t in low for t in targets):
            problems.append(seg)
        elif "codebase" in low:
            problems.append(seg)
        elif YEARS_RE.search(seg):
            problems.append(seg)
        elif not any(k in low for k in REAL_CLAIM_KEYS):
            problems.append(seg)
    return problems


def safe_pr_body(deal):
    """Than PR an toan khi ban goc bi LINT chan: chi thong tin trung tinh +
    ho so that, khong nhan kinh nghiem, khong placeholder."""
    return ("Pull request prepared by PepperResearch (GitHub: Luando-tester) for this issue.\n\n"
            "Profile: " + REAL_PROFILE + "\n\n"
            "The deliverable files are included in this PR for review. Happy to adjust "
            "based on feedback - thank you!")


def gate_outbound_text(text, deal, kind="apply"):
    """CHOT CHAN CUOI cho MOI text gui ra ngoai (comment don/claim/follow-up
    va than PR): chay LINT nghiem; co cau nhan kinh nghiem bia thi THAY TOAN
    BO text bang template an toan (chi so that + ke hoach chung + loi xin
    duoc giao viec) - khong bao gio gui text goc. Tra (text_an_toan, problems).
    kind='apply' -> template_apply; kind='pr' -> safe_pr_body."""
    problems = lint_application(text, deal)
    if not problems:
        return text, []
    safe = template_apply(deal) if kind == "apply" else safe_pr_body(deal)
    return sanitize_comment_body(safe), problems


def prompt_apply(deal, info):
    p = ("Ban la PepperResearch, freelancer dang XIN NHAN 1 keo GitHub bounty. "
         "Viet 1 comment tieng Anh ngan gon, chuyen nghiep, de dang len issue xin duoc giao viec:\n"
         "- Gioi thieu 1 cau: CHI duoc dua tren HO SO THAT duoi day - chi lien he nang luc "
         "CHUYEN DOI duoc sang loai keo nay. TUYET DOI KHONG nhan kinh nghiem voi "
         "repo/project/codebase dich, khach hang cu, hay bat ky thu gi ngoai ho so that.\n"
         "HO SO THAT (nguon duy nhat duoc phep dung): " + REAL_PROFILE + "\n"
         "- Ke hoach lam 3-5 buoc cu the theo noi dung issue.\n"
         "- ETA uoc luong: ghi SO NGAY cu the (mac dinh 3 ngay neu chua chac) - "
         "TUYET DOI khong de placeholder dang [X].\n"
         "- Ket: nho chu issue assign / xac nhan cho bat dau.\n"
         "Chi tra ve dung noi dung comment, khong giai thich them.\n\n"
         + deal_context(deal, info))
    if not deal.get("budget_usd"):
        p += ("\n\nQUAN TRONG: keo CHUA ghi ngan sach - gop luon doan hoi tien nay vao cuoi comment "
              "(nguyen van y): " + ASK_MONEY_EN)
    return p


def sanitize_comment_body(text):
    """Than comment GUI DI khong duoc con placeholder dang [X]/[...] (don mau
    cu tung de 'ETA: [X] days'). Thay bang gia tri mac dinh hop ly: [X] days
    -> 3 days, [X] -> 3. Khong dong vao link markdown [text](url) vi mau chi
    bat dung chu X trong ngoac vuong."""
    t = text or ""
    t = re.sub(r"\[\s*X\s*\]\s*days?", "3 days", t, flags=re.I)
    t = re.sub(r"\[\s*X\s*\]", "3", t, flags=re.I)
    return t


def ensure_ask_money(text, deal):
    """Bao dam don cua keo CHUA ghi ngan sach LUON co doan hoi tien bat buoc:
    Gemini co the quen chen -> code tu noi them ASK_MONEY_EN (khong sua don
    da co san doan hoi: nhan dien bang cum 'exact bounty amount')."""
    if deal.get("budget_usd"):
        return text
    if "exact bounty amount" in (text or ""):
        return text
    return (text or "").rstrip() + "\n\n" + ASK_MONEY_EN


def template_apply(deal):
    lines = [
        "Hi! I'm PepperResearch — I'd like to take on this issue.",
        "",
        "My plan: 1) study the task and the codebase/materials, 2) implement it in a "
        "separate branch / draft, 3) test it locally against the requirements, "
        "4) open a pull request / deliver the work referencing this issue.",
        "My ETA is 3 days from assignment. If the task is still open, please assign "
        "it to me or confirm that I can proceed. Thank you!",
    ]
    if not deal.get("budget_usd"):
        lines += ["", ASK_MONEY_EN]
    return "\n".join(lines)


def prompt_product(deal, info, typ):
    ctx = deal_context(deal, info)
    if typ == "viet":
        return ("Ban la nguoi lam noi dung chuyen nghiep. Hay LAM THAT san pham cho keo viet "
                "duoi day: bai viet/tai lieu HOAN CHINH dung yeu cau issue, dung ngon ngu cua "
                "issue, cau truc ro rang, san sang nop. Neu la research: chi dung thong tin "
                "trong issue/pack va kien thuc chac chan; so lieu/link chua chac thi ghi ro "
                "'can kiem chung' - TUYET DOI khong bia so lieu hay link. Neu co tu gioi thieu, "
                "CHI duoc dung ho so that nay, khong nhan kinh nghiem ngoai ho so: "
                + REAL_PROFILE + "\n\n" + ctx)
    if typ == "khac":
        return ("Hay LAM THAT san pham cho keo duoi day (tai lieu/ke hoach/ban thao dung "
                "yeu cau issue, cau truc ro, san sang nop). Khong bia so lieu. Neu co tu gioi "
                "thieu, CHI duoc dung ho so that nay, khong nhan kinh nghiem ngoai ho so: "
                + REAL_PROFILE + "\n\n" + ctx)
    return ""


def template_product(deal, typ):
    return ("# San pham (khung template offline - chua co Gemini)\n\n"
            "- Keo: %s\n- Link: %s\n- Loai: %s\n- Ngan sach: %s\n\n"
            "## Yeu cau\n%s\n\n## Khung lam\n1. Doc ky issue. 2. Lam theo yeu cau. "
            "3. Tu kiem tra. 4. Nop kem bang chung.\n"
            % (deal["title"], deal["url"], typ,
               ("$" + str(deal["budget_usd"])) if deal.get("budget_usd") else "CHUA GHI",
               (deal.get("pack") or "")[:2500]))


def prompt_solution(deal, info):
    return ("Ban la ky su phan mem. Phan tich keo code duoi day va viet SOLUTION.md: "
            "1) Tom tat yeu cau + tieu chi nghiem thu trich tu issue; 2) Cach tiep can ky "
            "thuat tung buoc; 3) File/duong dan du kien sua (theo cau truc repo neu thay "
            "trong issue, chua chac thi ghi ro la du kien); 4) Ke hoach tu test. "
            "Khong bia chi tiet khong co trong issue.\n\n" + deal_context(deal, info))


def prompt_code(deal, info):
    return ("Ban la ky su phan mem. Dua tren keo code duoi day, viet code NHAP san sang "
            "dan vao repo. Dinh dang bat buoc cho MOI file:\n"
            "=== FILE: duong/dan/file.ext ===\n<toan bo noi dung file>\n=== END FILE ===\n"
            "Chi tra ve cac khoi file, toi da 4 file quan trong nhat, khong giai thich ngoai khoi.\n\n"
            + deal_context(deal, info))


def parse_code_files(text):
    files = []
    pat = re.compile(r"=== FILE: (.+?) ===\s*\n(.*?)\n=== END FILE ===", re.S)
    for m in pat.finditer(text or ""):
        path = m.group(1).strip().replace("\\", "/")
        if path.startswith("/") or ".." in path.split("/"):
            continue
        files.append((path, m.group(2)))
    return files


# ---------------------------------------------------------------- File helpers
def deal_dir(slug):
    d = os.path.join(DELIV_DIR, slug)
    os.makedirs(d, exist_ok=True)
    return d


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return os.path.relpath(path, BASE_DIR)


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- Hanh dong chinh
def make_apply(entry, pool, pool_state, info):
    """Sinh APPLY.md (don xin nhan viec). Co PAT thi gui comment that ngay."""
    notify_started(entry)
    # CONG KIEM CHUNG TRUOC GUI: fetch lai info MOI NHAT - khong co tin hieu
    # tien that thi CHAN ngay, khong soan khong gui (bai hoc SS14#44876).
    fresh = fetch_issue_info(entry["url"])
    ok_v, reason_v = presend_verify(entry, fresh if fresh is not None else info)
    if not ok_v:
        block_presend(entry, reason_v)
        return entry
    deal = {"title": entry["title"], "url": entry["url"], "budget_usd": entry.get("budget_usd"),
            "pack": entry.get("pack", "")}
    if pool:
        text, mode = gemini_generate_pool(pool, pool_state, prompt_apply(deal, info))
        if not text:
            text = template_apply(deal)
    else:
        text, mode = template_apply(deal), "template (chua co Gemini key)"
    comment_body = sanitize_comment_body(ensure_ask_money(text.strip(), deal))
    # LINT NGHIEM (gate_outbound_text): don nhan kinh nghiem khong co trong
    # ho so that -> VUT TOAN BO, thay bang template an toan (chi ho so that
    # + ke hoach chung), khong bao gio gui text goc.
    comment_body, bia = gate_outbound_text(comment_body, deal, kind="apply")
    if bia:
        log("LINT chan don bia cho %s: %s" % (entry["url"], " | ".join(bia)[:200]))
        mode = mode + " | don Gemini bi LINT chan (bia kinh nghiem) -> template an toan"
        entry["apply_lint_blocked"] = bia[:3]
    doc = (NOTE_DRAFT
           + "# Don xin nhan viec (APPLY) - %s\n\n- Keo: %s\n- Link: %s\n- Mode: cho_duoc_chon\n"
             "- Nguon soan: %s\n- Trang thai gui: %s\n\n## Noi dung comment se gui\n\n%s\n"
           % (entry["title"], entry["title"], entry["url"], mode,
              "se gui bang GITHUB_PAT ngay sau khi luu" if os.environ.get("GITHUB_PAT") else "CHO PAT - chua gui",
              comment_body))
    rel = write_file(os.path.join(deal_dir(entry["slug"]), "APPLY.md"), doc)
    entry.setdefault("files", []).append(rel)
    entry["apply_mode"] = mode
    entry["status"] = "applied"
    entry["applied_at"] = now_iso()
    entry["apply_sent"] = False
    if (os.environ.get("GITHUB_PAT") or "").strip():
        # DEDUPE TRUOC GUI: GET lai comment cua issue ngay truoc khi POST -
        # da co comment cua Luando-tester thi danh dau da gui, KHONG gui trung
        # (doc lap voi state, cuu truong hop run truoc bi huy truoc commit).
        dup, dup_url = already_commented(entry["url"])
        if dup:
            entry["apply_sent"] = True
            entry["apply_comment_url"] = dup_url
            entry["apply_dedupe_skip"] = "da co comment cua Luando-tester tren issue - khong gui trung"
            log("DEDUPE: bo qua gui don (da co comment cua minh): %s" % entry["url"])
        else:
            p = parse_issue_url(entry["url"])
            if p:
                st, d = gh_api("POST", "/repos/%s/%s/issues/%d/comments" % p, {"body": comment_body})
                if st in (200, 201):
                    entry["apply_sent"] = True
                    entry["apply_comment_url"] = (d or {}).get("html_url", "")
                    log("Da GUI don xin viec: %s" % entry["url"])
                else:
                    log("Gui don loi HTTP %s cho %s - don van nam o APPLY.md" % (st, entry["url"]))
                    if st == 403:
                        entry["apply_blocked"] = ("PAT fine-grained khong comment duoc repo nguoi khac "
                                                   "(HTTP 403) - can classic PAT scope public_repo")
                        # Co cho-token rieng: chu ky khac van chay binh thuong; chi
                        # thu gui lai khi van tay PAT thay doi (da thay token moi).
                        entry["awaiting_token"] = True
                        entry["blocked_pat_fp"] = pat_fingerprint()
    telegram_send("[Pepper Hunter Doer] %s DON XIN VIEC\n%s\nLink: %s\nMode: cho duoc chon - %s"
                  % ("DA GUI" if entry["apply_sent"] else "DA SOAN (CHO PAT DE GUI)",
                     entry["title"], entry["url"],
                     "da gui comment xin nhan viec" if entry["apply_sent"]
                     else "don o APPLY.md, co PAT la gui ngay"))
    return entry


def make_product(entry, pool, pool_state, info):
    """Lam SAN PHAM that cho keo (chi goi khi lam_ngay hoac da assigned)."""
    notify_started(entry)
    deal = {"title": entry["title"], "url": entry["url"], "budget_usd": entry.get("budget_usd"),
            "pack": entry.get("pack", "")}
    typ = entry["type"]
    d = deal_dir(entry["slug"])
    made = []
    if typ == "code":
        if pool:
            sol, m1 = gemini_generate_pool(pool, pool_state, prompt_solution(deal, info))
            code_text, m2 = gemini_generate_pool(pool, pool_state, prompt_code(deal, info))
            if not sol:
                sol = template_product(deal, typ)
            modes = m1 + " | " + m2
        else:
            sol, code_text, modes = template_product(deal, typ), "", "template (chua co Gemini key)"
        made.append(write_file(os.path.join(d, "SOLUTION.md"), NOTE_DRAFT + sol + "\n"))
        files = parse_code_files(code_text)
        if files:
            for path, content in files[:4]:
                made.append(write_file(os.path.join(d, path), content + "\n"))
        elif code_text:
            made.append(write_file(os.path.join(d, "code-draft.md"), NOTE_DRAFT + code_text + "\n"))
        else:
            # Gemini khong sinh duoc code nhap (het pool/loi): van phai co san
            # pham khung ro nhan de keo khong chet dung - SOLUTION.md o tren da
            # la ban template, them code-draft.md ghi ro tinh trang + khung lam.
            made.append(write_file(os.path.join(d, "code-draft.md"),
                                   NOTE_DRAFT
                                   + "# Code nhap - CHUA SINH DUOC (Gemini loi/het pool)\n\n"
                                   + "Trang thai: khung cho san - se sinh lai code nhap o vong sau "
                                     "khi Gemini phuc hoi, hoac lam tay theo SOLUTION.md.\n\n"
                                   + template_product(deal, typ) + "\n"))
            entry["product_incomplete"] = "code draft chua sinh duoc - cho Gemini phuc hoi"
        entry["product_mode"] = modes
    else:
        if pool:
            text, m = gemini_generate_pool(pool, pool_state, prompt_product(deal, info, typ))
            if not text:
                text = template_product(deal, typ)
        else:
            text, m = template_product(deal, typ), "template (chua co Gemini key)"
        made.append(write_file(os.path.join(d, "SAN-PHAM.md"), NOTE_DRAFT + text + "\n"))
        entry["product_mode"] = m
    entry.setdefault("files", []).extend(made)
    entry["files"] = sorted(set(entry["files"]))
    entry["status"] = "working"
    entry["product_at"] = now_iso()
    log("Da lam san pham (%s): %s -> %s" % (typ, entry["title"][:60], ", ".join(made)))
    return entry


def ensure_apply_file_money(entry):
    """Keo applied CHUA ghi ngan sach ma APPLY.md (soan tu cac lan chay truoc)
    thieu doan hoi tien bat buoc -> noi ASK_MONEY_EN vao cuoi than comment
    trong file (than comment nam o section cuoi cua APPLY.md). Chay moi vong
    cho den khi don duoc gui; da co doan hoi thi khong lam gi."""
    if entry.get("budget_usd") or entry.get("apply_sent"):
        return
    rel = None
    for f in entry.get("files", []):
        if f.endswith("APPLY.md"):
            rel = f
            break
    if not rel:
        return
    full = os.path.join(BASE_DIR, rel)
    if not os.path.isfile(full):
        return
    with open(full, encoding="utf-8") as fh:
        doc = fh.read()
    if "exact bounty amount" in doc:
        return
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(doc.rstrip() + "\n\n" + ASK_MONEY_EN + "\n")
    entry["apply_money_ensured"] = True
    log("Da bo sung doan hoi tien vao APPLY.md cua %s" % entry["url"])


def resend_apply(entry):
    """Gui LAI don cho entry 'applied' ma don chua gui duoc (lan chay truoc bi
    hong kenh: secret Telegram/PAT rong gia tri). Than comment lay tu APPLY.md.
    Loi 403-do-token -> co rieng awaiting_token: KHONG thu lai bang token cu
    (vo ich), chi thu lai ngay khi van tay PAT thay doi (Luan da thay classic
    PAT) - chu ky xu ly cac viec khac khong bi anh huong. Loi tam thoi khac:
    thu lai sau toi da 30 phut (RESEND_BACKOFF_SEC)."""
    if entry.get("apply_sent"):
        return True
    if not (os.environ.get("GITHUB_PAT") or "").strip():
        return False
    if entry.get("apply_blocked"):
        fp = pat_fingerprint()
        old_fp = entry.get("blocked_pat_fp")
        if old_fp and fp == old_fp:
            # Van la token da tung 403 -> cho token thay, khong thu lai vo ich.
            return False
        if old_fp and fp != old_fp:
            # Token da thay -> mo co, xoa blocked cu, thu gui ngay vong nay.
            entry.pop("awaiting_token", None)
            entry.pop("apply_blocked", None)
            entry.pop("blocked_pat_fp", None)
            entry.pop("apply_send_tried_at", None)
            log("Phat hien PAT da thay - mo lai gui don cho %s" % entry["url"])
        # old_fp rong = entry blocked tu code cu (chua ghi van tay): roi xuong
        # duoi thu gui 1 lan; neu lai 403 se ghi van tay + co awaiting_token.
    last = entry.get("apply_send_tried_at")
    if last:
        try:
            dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - dt).total_seconds() < RESEND_BACKOFF_SEC:
                return False
        except Exception:
            pass
    rel = None
    for f in entry.get("files", []):
        if f.endswith("APPLY.md"):
            rel = f
            break
    if not rel:
        return False
    full = os.path.join(BASE_DIR, rel)
    if not os.path.isfile(full):
        return False
    with open(full, encoding="utf-8") as fh:
        doc = fh.read()
    if "## Noi dung comment se gui" not in doc:
        return False
    comment_body = sanitize_comment_body(doc.split("## Noi dung comment se gui", 1)[1].strip())
    # LINT NGHIEM cho ca don cu soan tu cac lan chay truoc (gate_outbound_text):
    # co cau nhan kinh nghiem khong co trong ho so that -> thay TOAN BO bang
    # template an toan, khong gui text goc.
    deal_r = {"title": entry["title"], "url": entry["url"], "budget_usd": entry.get("budget_usd")}
    comment_body, bia = gate_outbound_text(comment_body, deal_r, kind="apply")
    if bia:
        log("LINT chan don gui bo sung (bia kinh nghiem) cho %s: %s - thay bang template an toan"
            % (entry["url"], " | ".join(bia)[:200]))
        entry["apply_lint_blocked"] = bia[:3]
    p = parse_issue_url(entry["url"])
    if not p or not comment_body:
        return False
    # DEDUPE TRUOC GUI ( nhu make_apply): da co comment cua minh tren issue
    # thi danh dau da gui va dung lai - day la duong gui trung chinh trong su
    # co IES (run truoc gui that nhung state chua kip commit).
    dup, dup_url = already_commented(entry["url"])
    if dup:
        entry["apply_sent"] = True
        entry["apply_comment_url"] = dup_url
        entry["apply_dedupe_skip"] = "da co comment cua Luando-tester tren issue - khong gui trung"
        entry.pop("awaiting_token", None)
        entry.pop("blocked_pat_fp", None)
        log("DEDUPE: bo qua gui bo sung (da co comment cua minh): %s" % entry["url"])
        return True
    entry["apply_send_tried_at"] = now_iso()
    st, d = gh_api("POST", "/repos/%s/%s/issues/%d/comments" % p, {"body": comment_body})
    if st in (200, 201):
        entry["apply_sent"] = True
        entry["apply_comment_url"] = (d or {}).get("html_url", "")
        entry.pop("awaiting_token", None)
        entry.pop("blocked_pat_fp", None)
        telegram_send("[Pepper Hunter Doer] DA GUI DON XIN VIEC (gui bo sung)\n%s\nLink: %s"
                      % (entry["title"], entry["url"]))
        log("Da gui bo sung don: %s" % entry["url"])
        return True
    log("Gui bo sung don loi HTTP %s cho %s" % (st, entry["url"]))
    if st == 403:
        entry["apply_blocked"] = ("PAT fine-grained khong comment duoc repo nguoi khac "
                                   "(HTTP 403) - can classic PAT scope public_repo")
        entry["awaiting_token"] = True
        entry["blocked_pat_fp"] = pat_fingerprint()
    return False


def check_assignment(entry):
    """Kiem tra don dang cho: duoc giao chua? Tra (verdict, ly_do):
    verdict = 'assigned'|'lost'|'het_han'|None; ly_do phuc vu tin Telegram
    khi thua (issue da dong / da giao cho ai)."""
    info = fetch_issue_info(entry["url"])
    if not info:
        return None, ""
    if OUR_USERNAME in (info.get("assignees") or []):
        return "assigned", ""
    labels = [l.lower() for l in (info.get("labels") or [])]
    if "assigned" in labels or "in-progress" in labels or "in progress" in labels:
        return "assigned", ""
    comments = fetch_issue_comments(entry["url"])
    for c in comments:
        body = (c.get("body") or "").lower()
        if OUR_USERNAME.lower() in body and any(w in body for w in ASSIGN_CONFIRM_WORDS):
            return "assigned", ""
        if (c.get("association") in ("OWNER", "MEMBER", "COLLABORATOR")
                and "assign" in body and OUR_USERNAME.lower() in body):
            return "assigned", ""
    if info.get("state") == "closed":
        return "lost", "issue da dong"
    others = [a for a in (info.get("assignees") or []) if a != OUR_USERNAME]
    if others:
        return "lost", "da giao cho " + ", ".join("@" + a for a in others)
    try:
        applied = datetime.fromisoformat(entry.get("applied_at", "").replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - applied).days >= APPLIED_EXPIRE_DAYS:
            return "het_han", "cho qua %d ngay khong duoc phan hoi" % APPLIED_EXPIRE_DAYS
    except Exception:
        pass
    return None, ""


def notify_application_ended(entry, verdict, reason):
    """Bao Telegram khi 1 don cho ket thuc ma khong duoc chon: thua nguoi
    khac (lost) hoac het han cho (het_han). Chi goi o vong CHUYEN trang thai
    nen moi keo chi nhan dung 1 tin."""
    if verdict == "lost":
        telegram_send("[Pepper Hunter Doer] KEO VE NGUOI KHAC (thua)\n%s\nLink: %s\nLy do: %s"
                      % (entry["title"], entry["url"], reason or "khong ro"))
    elif verdict == "het_han":
        telegram_send("[Pepper Hunter Doer] DON HET HAN CHO (%d ngay khong phan hoi)\n%s\nLink: %s"
                      % (APPLIED_EXPIRE_DAYS, entry["title"], entry["url"]))


def maybe_upgrade_mode(entry, pool, pool_state):
    """Phan loai lai 1 keo dang APPLIED theo tin hieu MOI NHAT (ap dung hoi to
    + bat tin hieu moi giua chung): quet lai mo ta issue hien tai + comment
    cua maintainer (OWNER/MEMBER/COLLABORATOR).
    - Xuat hien tin hieu CAM lam truoc -> giu cho_duoc_chon, ghi mode_reason.
    - Xuat hien tin hieu MOI LAM NGAY (vd maintainer comment 'go ahead') ->
      nang len lam_ngay: lam san pham ngay + mo PR nhap ngay (neu co PAT).
    - Van im lang -> giu cho_duoc_chon, mode_reason ghi ro ly do.
    Khong bao gio HA nhanh 1 keo da o lam_ngay. Tra True neu vua nang nhanh."""
    if entry.get("mode") == "lam_ngay":
        return False
    info = fetch_issue_info(entry["url"])
    # Tin hieu MOI NHAT thang: comment cua maintainer luon moi hon mo ta issue
    # (vd mo ta ghi 'first pr' nhung maintainer vua comment 'ask before
    # working' thi phai theo comment). Co tin hieu trong comment thi dung
    # comment, khong co moi xet mo ta.
    comments = fetch_issue_comments(entry["url"]) or []
    mtext = " ".join((c.get("body") or "") for c in comments
                     if c.get("association") in ("OWNER", "MEMBER", "COLLABORATOR")).lower()
    a, o = detect_signals(mtext)
    src = "comment maintainer"
    if not a and not o:
        low = ((entry.get("title") or "") + " " + ((info or {}).get("body") or "")
               + " " + (entry.get("pack") or "")).lower()
        a, o = detect_signals(low)
        src = "mo ta issue"
    if a:
        reason = ("phan loai lai: xuat hien tin hieu cam lam truoc '%s' (%s) "
                  "-> giu cho duoc chon" % (a, src))
        if entry.get("mode_reason") != reason:
            entry["mode_reason"] = reason
        return False
    if o:
        # Nang nhanh = sap lam san pham + mo PR: phai qua kiem chung truoc gui.
        ok_v, reason_v = presend_verify(entry, info)
        if not ok_v:
            entry["mode_reason"] = "khong nang lam_ngay - kiem chung truoc gui chan: " + reason_v
            log("Khong nang lam_ngay %s: %s" % (entry["url"], reason_v))
            return False
        entry["mode"] = "lam_ngay"
        entry["mode_reason"] = ("phan loai lai: issue noi ro moi lam ngay '%s' (%s) "
                                "-> lam san pham + mo PR nhap ngay, khong cho assign" % (o, src))
        log("Nang nhanh lam_ngay (tin hieu '%s' tu %s): %s" % (o, src, entry["title"][:70]))
        make_product(entry, pool, pool_state, info)
        if entry.get("status") == "working" and (os.environ.get("GITHUB_PAT") or "").strip():
            submit_github(entry)
        return True
    reason = "issue im lang (khong moi lam ngay, khong cam) -> mac dinh cho duoc chon"
    if entry.get("mode_reason") != reason:
        entry["mode_reason"] = reason
    return False


def load_meta():
    try:
        with open(META_PATH, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_meta(meta):
    os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def maybe_send_soak_report(state):
    """Tin TONG HOP toi da 1 lan/ngay (tinh theo ngay VN): liet ke cac don
    applied cho >= SOAK_MIN_DAYS ngay chua co phan hoi (van con o trang thai
    applied). Moc ngay da gui luu o state/doer_meta.json (commit cung state
    de khong gui lap giua cac run). Tra True neu vua gui thanh cong."""
    today = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d")
    meta = load_meta()
    if meta.get("soak_report_date") == today:
        return False
    waiting = []
    now = datetime.now(timezone.utc)
    for e in state.values():
        if not isinstance(e, dict) or e.get("status") != "applied":
            continue
        try:
            applied = datetime.fromisoformat((e.get("applied_at") or "").replace("Z", "+00:00"))
        except Exception:
            continue
        days = (now - applied).days
        if days >= SOAK_MIN_DAYS:
            waiting.append((days, e))
    if not waiting:
        return False
    waiting.sort(key=lambda kv: -kv[0])
    lines = ["[Pepper Hunter Doer] DON DANG NGAM - %d don cho >= %d ngay chua phan hoi:"
             % (len(waiting), SOAK_MIN_DAYS)]
    for days, e in waiting[:15]:
        lines.append("- %s - cho %d ngay\n  %s" % (e.get("title", ""), days, e.get("url", "")))
    if len(waiting) > 15:
        lines.append("... va %d don nua" % (len(waiting) - 15))
    if telegram_send("\n".join(lines)):
        meta["soak_report_date"] = today
        save_meta(meta)
        log("Da gui tin tong hop don dang ngam (%d don)" % len(waiting))
        return True
    return False


def submit_github(entry):
    """Nop bai kenh GitHub bang PAT: fork -> branch -> commit file san pham -> PR.
    Tra True neu da mo duoc PR. Chi chay khi co GITHUB_PAT."""
    p = parse_issue_url(entry["url"])
    if not p:
        return False
    # CHOT CHAN CUOI cho PR: kiem chung lai tin hieu tien that ngay truoc khi
    # fork/mo PR - chan ca cac keo da dang ky tu truoc khi co cong nay.
    ok_v, reason_v = presend_verify(entry, fetch_issue_info(entry["url"]))
    if not ok_v:
        if entry.get("presend_blocked_reason") != reason_v:
            entry["presend_blocked_reason"] = reason_v
            log("submit_github BI CHAN boi kiem chung truoc gui (%s): %s" % (entry["url"], reason_v))
        return False
    owner, repo, number = p
    st, me = gh_api("GET", "/user")
    if st != 200:
        log("PAT khong doc duoc /user (HTTP %s) - chua nop duoc" % st)
        return False
    me_login = me.get("login")
    st, fork = gh_api("POST", "/repos/%s/%s/forks" % (owner, repo), {})
    if st not in (200, 201, 202):
        log("Fork loi HTTP %s cho %s/%s" % (st, owner, repo))
        return False
    base_sha = None
    default_branch = None
    for _ in range(10):
        st, fr = gh_api("GET", "/repos/%s/%s" % (me_login, repo))
        if st == 200:
            default_branch = fr.get("default_branch") or "main"
            st2, ref = gh_api("GET", "/repos/%s/%s/git/ref/heads/%s" % (me_login, repo, default_branch))
            if st2 == 200:
                base_sha = ((ref.get("object") or {}).get("sha"))
                if base_sha:
                    break
        time.sleep(6)
    if not base_sha:
        log("Fork chua san sang (khong lay duoc sha nhanh mac dinh) - de vong sau nop")
        return False
    branch = entry.get("submit_branch") or ("pepper-hunter/issue-%d" % number)
    gh_api("POST", "/repos/%s/%s/git/refs" % (me_login, repo),
           {"ref": "refs/heads/" + branch, "sha": base_sha})
    uploaded = []
    for rel in entry.get("files", []):
        name = os.path.basename(rel)
        if name in ("APPLY.md",):
            continue
        full = os.path.join(BASE_DIR, rel)
        if not os.path.isfile(full):
            continue
        with open(full, "rb") as f:
            import base64
            content_b64 = base64.b64encode(f.read()).decode()
        target = "pepper-hunter-deliverable/" + name
        st, _d = gh_api("PUT", "/repos/%s/%s/contents/%s" % (me_login, repo, target),
                        {"message": "Pepper Hunter: deliverable for #%d" % number,
                         "content": content_b64, "branch": branch})
        if st in (200, 201):
            uploaded.append(target)
    if not uploaded:
        log("Khong upload duoc file nao len fork - chua nop")
        return False
    body = ("Deliverable prepared by PepperResearch (Pepper Hunter Doer) for #%d.\n\n"
            "Files under `pepper-hunter-deliverable/`: %s\n\n%s"
            % (number, ", ".join(uploaded),
               "This is a draft PR for review." if PR_DRAFT else "Ready for review."))
    # Than PR cung la text ra ngoai -> qua LINT nghiem nhu moi duong gui khac
    # (du phong: sau nay co chen tu gioi thieu vao body cung khong bia duoc).
    body, bia_pr = gate_outbound_text(body, {"title": entry["title"], "url": entry["url"],
                                             "budget_usd": entry.get("budget_usd")}, kind="pr")
    if bia_pr:
        log("LINT chan than PR bia cho %s - thay bang body an toan" % entry["url"])
        entry["pr_lint_blocked"] = bia_pr[:3]
    st, pr = gh_api("POST", "/repos/%s/%s/pulls" % (owner, repo),
                    {"title": "[Pepper Hunter] %s" % entry["title"][:90],
                     "head": "%s:%s" % (me_login, branch), "base": default_branch,
                     "body": body, "draft": PR_DRAFT})
    if st in (200, 201):
        entry["pr_url"] = pr.get("html_url", "")
        entry["pr_number"] = pr.get("number")
        entry["submit_branch"] = branch
        entry["status"] = "submitted"
        entry["submitted_at"] = now_iso()
        telegram_send("[Pepper Hunter Doer] DA NOP BAI\n%s\nPR: %s" % (entry["title"], entry["pr_url"]))
        log("Da nop PR: %s" % entry["pr_url"])
        return True
    log("Mo PR loi HTTP %s cho %s" % (st, entry["url"]))
    return False


def check_submitted(entry):
    """submitted -> cho_tra khi PR merged hoac chu xac nhan xong."""
    p = parse_issue_url(entry["url"])
    if not p or not entry.get("pr_number"):
        return False
    st, pr = gh_api("GET", "/repos/%s/%s/pulls/%d" % (p[0], p[1], entry["pr_number"]))
    if st == 200 and pr.get("merged"):
        entry["status"] = "cho_tra"
        entry["merged_at"] = now_iso()
        log("PR merged -> CHO TRA: %s" % entry["title"][:60])
        return True
    return False


# ---------------------------------------------------------------- STATUS + git
def write_status(state, latest_ts, registered_this_cycle=0, cycle_errors=0):
    counts = {}
    for e in state.values():
        counts[e.get("status", "?")] = counts.get(e.get("status", "?"), 0) + 1
    vn = datetime.now(timezone.utc) + timedelta(hours=7)
    lines = ["# Pepper Hunter Doer - STATUS",
             "",
             "Dang chay binh thuong - cap nhat %s VN, tong keo dang theo doi: %d, moi dang ky vong nay: %d, loi da cach ly vong nay: %d"
             % (vn.strftime("%H:%M"), len(state), registered_this_cycle, cycle_errors),
             "Cap nhat: %s (VN) / %s (UTC)" % (vn.strftime("%Y-%m-%d %H:%M:%S"),
                                               datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
             "Worker /latest ts: %s" % (latest_ts or "chua co"),
             "Tong keo da theo doi: %d" % len(state),
             "Trang thai: " + (", ".join("%s=%d" % kv for kv in sorted(counts.items())) or "chua co keo"),
             ""]
    order = [("applied", "Dang cho duoc chon (da nop don)"),
             ("assigned", "Da duoc chon - chuan bi lam"),
             ("working", "Dang lam / san pham da xong, cho nop"),
             ("submitted", "Da nop - cho duyet/merge"),
             ("cho_tra", "Cho tra (da xong, cho tien ve)"),
             ("da_tra", "Da tra (co bang chung)"),
             ("lost", "Thua / da co nguoi nhan / issue dong"),
             ("het_han", "Het han cho"),
             ("skipped_trap", "Bo qua - repo bay bot (khong dang ky, khong gui don)"),
             ("skipped_nopay", "Bo qua - khong co tin hieu tien that (kiem chung truoc gui chan)"),
             ("new", "Moi dang ky")]
    for status, label in order:
        rows = [e for e in state.values() if e.get("status") == status]
        if not rows:
            continue
        lines += ["## %s (%d)" % (label, len(rows)), ""]
        for e in sorted(rows, key=lambda x: x.get("updated_at", ""), reverse=True):
            budget = ("$" + str(e["budget_usd"])) if e.get("budget_usd") else "chua ghi ngan sach"
            extra = ""
            if e.get("pr_url"):
                extra = " - PR: " + e["pr_url"]
            elif status == "applied":
                if e.get("apply_sent"):
                    extra = " - don: da gui"
                elif e.get("apply_blocked"):
                    extra = " - don: CHUA GUI DUOC - " + e["apply_blocked"]
                    if e.get("awaiting_token"):
                        extra += " (dang cho classic PAT - tu gui lai ngay khi token thay)"
                else:
                    extra = " - don: da soan, CHO PAT de gui"
            elif status == "skipped_trap":
                extra = " - ly do: " + (e.get("note") or "repo bay bot")
            elif status == "skipped_nopay":
                extra = " - ly do: " + (e.get("note") or "khong co tin hieu tien that")
            if e.get("mode_reason") and status in ("new", "applied", "assigned", "working"):
                extra += " | mode_reason: " + e["mode_reason"]
            lines.append("- [%s](%s) - %s/%s - %s%s"
                         % (e["title"][:90], e["url"], e.get("mode", "?"), e.get("type", "?"),
                            budget, extra))
        lines.append("")
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def git_commit_push(msg):
    if not DOER_GIT:
        return
    def run(args):
        return subprocess.run(args, cwd=BASE_DIR, capture_output=True, text=True, timeout=120)
    try:
        run(["git", "add", "state/doer_state.json", "state/doer_meta.json", "STATUS.md", "deliverables"])
        st = run(["git", "status", "--porcelain"])
        if not (st.stdout or "").strip():
            return
        run(["git", "-c", "user.name=Pepper Hunter Doer", "-c", "user.email=doer@pepperresearch",
             "commit", "-m", msg])
        # actions/checkout de repo o detached HEAD -> phai push HEAD:main tuong minh,
        # "git push" tran se loi "not currently on a branch" va mat commit am tham.
        r = run(["git", "push", "origin", "HEAD:main"])
        if r.returncode != 0:
            log("git push loi: %s" % (r.stderr or "")[:200])
        else:
            log("Da commit+push: %s" % msg)
    except Exception as e:
        log("git loi: %s" % e)


def other_active_doer_run(env):
    """Co run doer.yml NAO KHAC dang active (queued/pending/in_progress)
    ngoai run hien tai khong? Dung gh api; tra True/False, None neu khong
    doc duoc (loi API/mang - nguoi goi tu quyet dinh theo huong an toan)."""
    try:
        r = subprocess.run(
            ["gh", "api", "repos/{owner}/{repo}/actions/workflows/doer.yml/runs?per_page=30",
             "--jq", ".workflow_runs[] | [.id, .status] | @tsv"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=60, env=env)
        if r.returncode != 0:
            return None
        me = (os.environ.get("GITHUB_RUN_ID") or "").strip()
        for line in (r.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            rid, status = parts[0].strip(), parts[1].strip()
            if rid != me and status in ("queued", "pending", "waiting", "in_progress"):
                return True
        return False
    except Exception:
        return None


def self_dispatch():
    if not DOER_DISPATCH:
        return
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        log("Khong co GH_TOKEN/GITHUB_TOKEN - khong tu dispatch duoc run moi")
        return
    env = dict(os.environ)
    env["GH_TOKEN"] = token
    # SINGLE-FLIGHT (bo sung sau su co IES - nhieu run dispatch de len nhau
    # sang 11/11): truoc khi tu dispatch, kiem tra con run doer.yml nao khac
    # dang active khong. Co -> KHONG dispatch nua: run do (hoac schedule */5)
    # se noi tiep chuoi, tranh 2 run cung ghi state/comment de len nhau.
    # Workflow doer.yml cung da co concurrency group lam lop chot sau.
    active = other_active_doer_run(env)
    if active:
        log("Bo qua tu dispatch: da co run doer.yml khac dang active (single-flight)")
        return
    if active is None:
        log("Khong kiem tra duoc run dang active - van dispatch (concurrency group cua workflow se chan trung)")
    try:
        r = subprocess.run(["gh", "workflow", "run", "doer.yml", "--ref", "main"],
                           cwd=BASE_DIR, capture_output=True, text=True, timeout=120, env=env)
        log("Tu dispatch run moi: rc=%d %s" % (r.returncode, (r.stdout + r.stderr)[:200]))
    except Exception as e:
        log("Dispatch loi: %s" % e)


# ---------------------------------------------------------------- Vong lap
def process_cycle(state, pool, pool_state):
    """1 vong: dang ky keo moi tu 2 nguon intake roi chay may trang thai.
    Tra dict {latest_ts, new_registered, changed} - main quyet dinh commit/heartbeat."""
    changed = False
    new_registered = 0
    cycle_errors = 0
    latest_ts = None
    pre_existing = set(state.keys())

    # --- Migration cong bay bot: keo da nam trong state ma thuoc repo bay ->
    # skipped_trap (khong gui don, khong xu ly nua) + bao Telegram 1 lan.
    # Nguon nhan dien: ten repo (trap_repo_reason) HOAC khung mo ta mirror
    # trong title/pack da luu (mirror_body_reason - bat duoc ho IES
    # "Conformance Mirror" ma ten repo khong co dau hieu gi).
    for url, entry in list(state.items()):
        if entry.get("status") in ("new", "applied", "assigned", "working"):
            reason = (trap_repo_reason(url)
                      or mirror_body_reason(entry.get("title"), entry.get("pack")))
            if reason:
                entry["status"] = "skipped_trap"
                entry["note"] = reason
                changed = True
                log("Chuyen skipped_trap: %s" % url)
        if entry.get("status") == "skipped_trap" and not entry.get("trap_notified"):
            if telegram_send("[Pepper Hunter Doer] BO QUA KEO BAY BOT (khong gui don)\n%s\nLink: %s\nLy do: %s"
                             % (entry["title"], url, entry.get("note", "repo bay bot"))):
                entry["trap_notified"] = True
                changed = True

    # --- Intake 1: Worker /latest (deals cua tick gan nhat + queue tich luy)
    # PHAI gui User-Agent rieng: Cloudflare chan UA mac dinh "Python-urllib"
    # (HTTP 403) - day la loi goc khien ban doer cu chet im lang o buoc nay:
    # no return som, bo qua ca vong gom ca ghi STATUS + commit.
    st, latest = http_json("GET", WORKER_URL + "/latest",
                           {"User-Agent": "pepper-hunter-doer/1.0"}, timeout=40)
    if st == 200 and isinstance(latest, dict):
        latest_ts = latest.get("ts")
        deals = list(latest.get("deals") or []) + list(latest.get("queue") or [])
        log("Vong moi: /latest ts=%s, %d keo trong bao cao (deals+queue)"
            % (latest_ts, len(deals)))
        seen_now = set()
        for deal in deals:
            url = deal.get("url")
            if not url or url in state or url in seen_now:
                continue
            seen_now.add(url)
            if new_registered >= MAX_NEW_PER_CYCLE:
                break
            try:
                if register_deal(state, deal) is not None:
                    new_registered += 1
                    changed = True
            except Exception as e:
                cycle_errors += 1
                log("Loi dang ky keo (intake 1) %s: %s" % (url, e))
    else:
        log("Doc /latest loi (HTTP %s) - van chay intake tu quet" % st)

    # --- Intake 2: tu quet GitHub Search (bat lai keo da troi khoi /latest)
    try:
        candidates = fetch_bounty_candidates()
    except Exception as e:
        log("Intake2 loi: %s" % e)
        candidates = []
    fresh = [c for c in candidates if c["url"] not in state]
    log("Intake2: %d ung vien sach, %d chua dang ky" % (len(candidates), len(fresh)))
    for deal in fresh:
        if new_registered >= MAX_NEW_PER_CYCLE:
            log("Da dat tran %d dang ky moi/vong - phan con lai de vong sau" % MAX_NEW_PER_CYCLE)
            break
        try:
            if register_deal(state, deal) is not None:
                new_registered += 1
                changed = True
        except Exception as e:
            cycle_errors += 1
            log("Loi dang ky keo (intake 2) %s: %s" % (deal.get("url"), e))

    # --- Backfill thong bao: keo dang ky tu cac lan chay bi hong kenh (secret
    # Telegram tung rong gia tri nen su kien dang ky chua bao gio gui duoc) ->
    # danh dau da bao + gui 1 tin TONG HOP duy nhat, khong ban lai tung su kien cu.
    backfilled = 0
    for url in pre_existing:
        e = state.get(url)
        if not e or e.get("status") in ("lost", "het_han", "pipeline-test", "skipped_trap", "skipped_nopay"):
            continue
        if not e.get("notified_registered"):
            e["notified_registered"] = True
            if e.get("status") in ("applied", "working", "submitted", "cho_tra", "da_tra"):
                e["notified_started"] = True
            backfilled += 1
    if backfilled:
        changed = True
        counts = {}
        for e in state.values():
            counts[e.get("status", "?")] = counts.get(e.get("status", "?"), 0) + 1
        telegram_send("[Pepper Hunter Doer] KENH THONG BAO DA SONG LAI - dang theo doi %d keo (%s). "
                      "Tu bay gio moi su kien (nhan keo moi / duoc chon / nop bai / tien ve) se bao ngay."
                      % (len(state), ", ".join("%s=%d" % kv for kv in sorted(counts.items()))))
        log("Backfill thong bao cho %d keo cu" % backfilled)

    # --- May trang thai (keo lam_ngay duoc UU TIEN xu ly dau vong - sort on
    # dinh: lam_ngay len truoc, cac keo con lai giu nguyen thu tu cu)
    ordered = sorted(state.items(), key=lambda kv: 0 if (kv[1] or {}).get("mode") == "lam_ngay" else 1)
    for url, entry in ordered:
        status = entry.get("status")
        before = json.dumps({k: v for k, v in entry.items() if k != "updated_at"},
                            sort_keys=True, ensure_ascii=False, default=str)
        try:
            if status == "new" and entry.get("mode") == "cho_duoc_chon":
                make_apply(entry, pool, pool_state, fetch_issue_info(url))
            elif status == "new" and entry.get("mode") == "lam_ngay":
                # Nhanh lam_ngay se mo PR ra ngoai -> cung phai qua kiem chung
                # truoc gui (chan keo ao/game truoc khi ton cong lam san pham).
                ok_v, reason_v = presend_verify(entry, fetch_issue_info(url))
                if not ok_v:
                    block_presend(entry, reason_v)
                else:
                    make_product(entry, pool, pool_state, fetch_issue_info(url))
                    # Lam xong la mo PR nhap NGAY trong cung vong (khong cho assign)
                    if entry.get("status") == "working" and (os.environ.get("GITHUB_PAT") or "").strip():
                        submit_github(entry)
            elif status == "applied":
                if not entry.get("apply_sent"):
                    ensure_apply_file_money(entry)
                    # Don cu chua gui duoc cung phai qua kiem chung truoc khi
                    # gui bo sung (keo dang ky tu truoc khi co cong nay).
                    ok_v, reason_v = presend_verify(entry, fetch_issue_info(url))
                    if not ok_v:
                        block_presend(entry, reason_v)
                    else:
                        resend_apply(entry)
                if entry.get("status") == "applied":
                    verdict, verdict_reason = check_assignment(entry)
                    if verdict == "assigned":
                        entry["status"] = "assigned"
                        entry["assigned_at"] = now_iso()
                        telegram_send("[Pepper Hunter Doer] DUOC CHON!\n%s\nLink: %s\nBat dau lam san pham ngay."
                                      % (entry["title"], url))
                        make_product(entry, pool, pool_state, fetch_issue_info(url))
                    elif verdict in ("lost", "het_han"):
                        entry["status"] = verdict
                        entry["note"] = "don cho ket thuc: " + verdict
                        notify_application_ended(entry, verdict, verdict_reason)
                    else:
                        # Chua co phan hoi: phan loai lai theo tin hieu moi nhat -
                        # issue vua moi lam ngay thi nang nhanh lam san pham ngay.
                        maybe_upgrade_mode(entry, pool, pool_state)
            elif status == "assigned":
                make_product(entry, pool, pool_state, fetch_issue_info(url))
            elif status == "working":
                # Keo goc applied duoc nang nhanh lam-ngay: van canh thua binh
                # thuong (issue dong / nguoi khac duoc giao -> lost + bao).
                if entry.get("apply_sent"):
                    v2, r2 = check_assignment(entry)
                    if v2 == "lost":
                        entry["status"] = "lost"
                        entry["note"] = "keo ve nguoi khac trong luc dang lam (PR nhap neu da mo thi bo)"
                        notify_application_ended(entry, "lost", r2)
                if entry.get("status") == "working":
                    if (os.environ.get("GITHUB_PAT") or "").strip():
                        submit_github(entry)
                    elif entry.get("note") != "san pham da xong - CHO PAT de nop PR":
                        entry["note"] = "san pham da xong - CHO PAT de nop PR"
            elif status == "submitted":
                check_submitted(entry)
            elif status == "da_tra" and not entry.get("paid_notified"):
                telegram_send("[Pepper Hunter Doer] TIEN VE!\n%s\nLink: %s" % (entry["title"], url))
                entry["paid_notified"] = True
        except Exception as e:
            cycle_errors += 1
            entry["last_error"] = "%s - %s" % (now_iso(), str(e)[:200])
            log("Loi xu ly keo %s: %s" % (url, e))
        after = json.dumps({k: v for k, v in entry.items() if k != "updated_at"},
                           sort_keys=True, ensure_ascii=False, default=str)
        if after != before:
            entry["updated_at"] = now_iso()
            changed = True

    # --- Nhac "don dang ngam": toi da 1 tin tong hop/ngay (moc trong meta file)
    try:
        if maybe_send_soak_report(state):
            changed = True
    except Exception as e:
        cycle_errors += 1
        log("Loi bao don dang ngam: %s" % e)

    if cycle_errors:
        log("Vong nay co %d loi da cach ly (khong chet vong)" % cycle_errors)
    save_state(state)
    return {"latest_ts": latest_ts, "new_registered": new_registered,
            "changed": changed, "errors": cycle_errors}


def main():
    pool = parse_key_pool()
    missing = []
    if not pool:
        missing.append("GEMINI_API_KEYS (dung template offline cho don/san pham)")
    if not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        missing.append("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (khong bao Telegram)")
    if not (os.environ.get("GITHUB_PAT") or "").strip():
        missing.append("GITHUB_PAT (don chi soan san, khong gui comment/khong mo PR)")
    for m in missing:
        log("chua cau hinh: " + m)
    log("Doer bat dau: pool %d key, budget %.0f phut, poll %ds, once=%s, git=%s, dispatch=%s"
        % (len(pool), LOOP_BUDGET_MIN, POLL_SEC, DOER_ONCE, DOER_GIT, DOER_DISPATCH))
    state = load_state()
    pool_state = {"dead": set(), "gone": {}}
    start = time.monotonic()
    budget_sec = LOOP_BUDGET_MIN * 60
    last_commit = 0.0  # monotonic cua lan commit+push gan nhat (heartbeat)
    while True:
        try:
            res = process_cycle(state, pool, pool_state)
        except Exception as e:
            # 1 vong loi la khong duoc giet ca job: log + van ghi heartbeat.
            log("LOI TOAN VONG (da cach ly, job van tiep tuc): %s" % e)
            res = {"latest_ts": None, "new_registered": 0, "changed": True, "errors": 1}
        heartbeat_due = (time.monotonic() - last_commit) >= HEARTBEAT_SEC
        if res["changed"] or heartbeat_due or DOER_ONCE:
            write_status(state, res["latest_ts"], res["new_registered"], res.get("errors", 0))
            git_commit_push("doer: vong %s - %d keo dang theo doi, moi dang ky %d"
                            % (datetime.now(timezone.utc).strftime("%H:%M"),
                               len(state), res["new_registered"]))
            last_commit = time.monotonic()
        if DOER_ONCE:
            log("DOER_ONCE=1 - thoat sau 1 vong")
            return 0
        elapsed = time.monotonic() - start
        remaining = budget_sec - elapsed
        if remaining <= 150:
            log("Sap het gio job (con %.0fs) - tu dispatch run moi roi thoat" % remaining)
            self_dispatch()
            return 0
        time.sleep(min(POLL_SEC, max(10, remaining - 120)))


if __name__ == "__main__":
    sys.exit(main())
