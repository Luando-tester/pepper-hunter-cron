#!/usr/bin/env python3
"""Pepper Hunter WATCHES - 7 watch kiem tien cua PepperResearch chay tren
GitHub Actions (port tu cron agent Muse o tab kiem tien, 10/11/2026).

Vong lap kieu DOER: moi 60s 1 vong, toi da ~330 phut, gan het gio thi tu
workflow_dispatch run moi (gh CLI + GITHUB_TOKEN cua run). Schedule */5
trong watch.yml chi la du phong danh thuc khi chuoi dut. State ben o
state/watches_state.json, mat tien trang thai o WATCHES.md - ca hai duoc
commit ve repo sau moi vong co thay doi (+ heartbeat dinh ky).

7 watch (moi watch 1 ham, cach ly loi tung watch - 1 nguon chet khong
keo chet ca vong):
  1. synmerco     - bang viec Synmerco: heartbeat/readiness/intents moi;
                    keo SACH -> BID NGAY gia that theo v69 (Luan chot
                    12/11: mac dinh 85% ngan sach, khong ha gia duoi doi
                    thu, khong vong lap ha gia); tu them capability khi
                    412. Can SYNMERCO_API_KEY.
  2. cc0          - don hang CC0 storefront: doc KV qua index
                    meta:recent_job_ids (ban va KV-429 06/11), bao don
                    PAID moi + probe test + tripwire coverage. Chi doc;
                    fulfill/sweep o phase 2 (Worker CC0). Can
                    CC0_CF_API_TOKEN (token Cloudflare doc KV).
  3. moltjobs     - MoltJobs: stats trigger (luon chay, public) +
                    heartbeat/assignment/job sach khi co MOLTJOBS_API_KEY;
                    ban dem 21:00-06:00 VN tu bid job sach da kiem chung
                    funded (ledger toi da 10 bid free/thang).
  4. owockibot    - bounty Owockibot: TU CLAIM bounty sach theo luat
                    Luan duyet 27/10 (chi can dia chi vi MetaMask cua
                    Luan - dia chi cong khai, khong can credential).
  5. fiverr       - hoat dong Fiverr seller: ban goc doc qua Gmail ->
                    CHO CONSENT Gmail OAuth (giai doan 2), chua port
                    phan doc mail.
  6. boards       - Superteam (+ RaptorX doi trang thai) / Taskmarket /
                    HYRVE / Frantic: keo moi qua cong sach -> bao.
  7. seller-inbox - hop thu Gumroad/Codester/Wirestock/Adobe/Upwork/
                    Dreamstime: phu thuoc Gmail OAuth -> CHO CONSENT
                    (giai doan 2), khong port phan doc mail.

CONG SACH (giu nguyen 100% luat cua Luan): sach, tien that da khoa
escrow/funded kiem chung duoc; bat nap tien/dat coc/phi kich hoat =
loai (dien nap tien thi PARK im lang); tien rut duoc ve vi Luan/PayPal;
loai tuyet doi shill/spam/fake engagement, ca cuoc/prediction, captcha
ho, stake-gated/referral ru agent, mule/rua tien, HUMAN_ONLY, site
credit/GMV gia. KHONG bao gio in gia tri bi mat ra log/Telegram.

Bien moi truong:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   bao Telegram (thieu -> bo qua)
  SYNMERCO_API_KEY    key agent Synmerco (thieu -> watch cho credential)
  MOLTJOBS_API_KEY    key agent MoltJobs (thieu -> chi stats chay)
  CC0_CF_API_TOKEN    token Cloudflare doc KV cc0-jobs (thieu -> cho)
  GH_TOKEN/GITHUB_TOKEN  cho gh tu dispatch run moi o cuoi job.
  WATCH_LOOP_BUDGET_MIN=330  WATCH_POLL_SEC=60  WATCH_ONCE=1
  WATCH_GIT=0 (tat commit)   WATCH_DISPATCH=0 (tat tu dispatch)
"""
import json, os, re, subprocess, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "state", "watches_state.json")
WATCHES_MD_PATH = os.path.join(BASE_DIR, "WATCHES.md")

LOOP_BUDGET_MIN = float(os.environ.get("WATCH_LOOP_BUDGET_MIN") or 330)
POLL_SEC = float(os.environ.get("WATCH_POLL_SEC") or 60)
WATCH_ONCE = (os.environ.get("WATCH_ONCE") or "") == "1"
WATCH_GIT = (os.environ.get("WATCH_GIT") or "1") != "0"
WATCH_DISPATCH = (os.environ.get("WATCH_DISPATCH") or "1") != "0"
HEARTBEAT_SEC = 900  # 15 phut: commit heartbeat ke ca khi khong doi

VN = timezone(timedelta(hours=7))
METAMASK_BASE = "0xd170ad7a09EC585Fcb37DC7a9C37d65b63783B61"
SOLANA_ADDR = "EMCzkUmfVLcbey2eugzppupQkz4Z8FiosLpMP9opUDv1"
CC0_ACCOUNT_ID = "90b86f24deb61d1b211e7acb6c1f5857"
UA = "pepper-hunter-watches/1.0"

# ------------------------------------------------------------------ log/time
def log(msg):
    print("[%s] %s" % (datetime.now(VN).strftime("%H:%M:%S"), msg), flush=True)

def now_vn():
    return datetime.now(VN)

def iso_vn(dt=None):
    return (dt or now_vn()).isoformat(timespec="seconds")

def is_night_vn(dt=None):
    h = (dt or now_vn()).hour
    return h >= 21 or h < 6

# ------------------------------------------------------------------ http
def http_req(method, url, headers=None, data=None, timeout=45):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", UA)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()
        except Exception:
            return e.code, b""
    except Exception as e:
        return 0, str(e).encode()

def http_json(method, url, headers=None, obj=None, timeout=45):
    data = None
    hdrs = dict(headers or {})
    if obj is not None:
        data = json.dumps(obj).encode()
        hdrs["Content-Type"] = "application/json"
    st, raw = http_req(method, url, hdrs, data, timeout)
    try:
        return st, json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return st, None

def http_curl(method, url, headers=None, obj=None, timeout=60):
    """curl fallback: server Synmerco/Superteam hay cat ket noi urllib
    (IncompleteRead) - ban goc cua cac watch nay cung dung curl."""
    args = ["curl", "-s", "-L", "--max-time", str(timeout), "-X", method,
            "-A", UA, "-w", "\n%{http_code}"]
    for k, v in (headers or {}).items():
        args += ["-H", "%s: %s" % (k, v)]
    if obj is not None:
        args += ["-H", "Content-Type: application/json", "-d", json.dumps(obj)]
    args.append(url)
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout + 15)
        out = r.stdout or ""
        body, _, code = out.rpartition("\n")
        st = int(code) if code.strip().isdigit() else 0
        try:
            return st, json.loads(body)
        except Exception:
            return st, None
    except Exception as e:
        return 0, None

# ------------------------------------------------------------------ telegram
# --- Nhip ban Telegram: toi thieu TG_MIN_GAP_SEC giua 2 tin lien tiep
# (ban loat cung luc bi Telegram 429 rot tin); gap 429 thi ton trong
# retry_after, cho roi gui lai toi da 2 lan. Dong bo voi doer.py.
TG_MIN_GAP_SEC = float(os.environ.get("TG_MIN_GAP_SEC") or 3.5)
_TG_LAST_SEND = [0.0]


def _tg_wait_turn():
    wait = _TG_LAST_SEND[0] + TG_MIN_GAP_SEC - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _TG_LAST_SEND[0] = time.monotonic()


def _tg_post_once(token, chat, text):
    st, raw = http_req("POST", "https://api.telegram.org/bot%s/sendMessage" % token,
                       {"Content-Type": "application/json"},
                       json.dumps({"chat_id": chat, "text": text[:3900]}).encode(), timeout=30)
    ok, retry_after = False, None
    try:
        d = json.loads(raw.decode("utf-8", "replace"))
        ok = st == 200 and d.get("ok") is True
        if not ok:
            retry_after = (d.get("parameters") or {}).get("retry_after")
    except Exception:
        ok = False
    return ok, st, retry_after


def telegram_send(text):
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chats = []
    for _k in ("TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID_2"):
        _c = (os.environ.get(_k) or "").strip()
        if _c and _c not in chats:
            chats.append(_c)
    if not token or not chats:
        log("Telegram chua cau hinh - bo qua bao: %s" % text.split(chr(10))[0][:80])
        return False
    ok_main = False
    for _i, chat in enumerate(chats):
        ok, st = False, 0
        for attempt in range(3):
            _tg_wait_turn()
            ok, st, retry_after = _tg_post_once(token, chat, text)
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
            log("Telegram gui loi (HTTP %s)" % st)
    return ok_main

# ------------------------------------------------------------------ cong sach
DIRTY_PATTERNS = [
    "shill", "fake engagement", "fake review", "fake reviews", "fake volume",
    "wash trading", "wash trade", "simulated volume", "bot traffic",
    "fake traffic", "generate gmv", "qualifying gmv", "site credit",
    "betting", "gambling", "prediction market", "captcha solving",
    "solve captcha", "bypass captcha", "money mule", "money laundering",
    "launder", "doxx", "doxing", "impersonat", "human_only", "human only",
    "stake to", "staking required", "deposit required", "deposit first",
    "activation fee", "pay a fee to", "referral recruitment",
    "recruit other agents", "recruit agents",
]
def dirty_hits(text):
    t = (text or "").lower()
    return [p for p in DIRTY_PATTERNS if p in t]

def parse_money(v):
    """Tra ve so USD (float) tu cac kieu gia tri hon tap; None neu khong ro."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"[\d][\d,]*\.?\d*", v.replace("$", ""))
        if m:
            try:
                return float(m.group(0).replace(",", ""))
            except Exception:
                return None
    return None

# ------------------------------------------------------------------ state
def default_state():
    return {
        "meta": {"created": iso_vn(), "launch_notified": False, "last_cycle": None,
                 "last_commit": None},
        "synmerco": {"status": "INIT", "seen_ids": [], "my_bids": {}, "pending": {},
                     "watch_ids": {}, "readiness_alerted": False,
                     "underbid_reject_alerted": {}, "last_check": None, "detail": ""},
        "cc0": {"status": "INIT", "kv_namespace_id": None, "reported_paid": [],
                "reported_test": [], "coverage_alerted_for": None,
                "last_check": None, "detail": ""},
        "moltjobs": {"status": "INIT", "seen_job_ids": [], "bid_ledger": {},
                     "stats_milestone": {"settled": None, "funded_employers": None},
                     "agent_status": None, "seen_assignments": [],
                     "last_check": None, "detail": ""},
        "owockibot": {"status": "INIT", "seen": {}, "active_claim": None,
                      "claims": [], "queued": [], "last_check": None, "detail": ""},
        "fiverr": {"status": "CHO-CONSENT", "last_check": None,
                   "detail": "Ban goc doc hoat dong qua Gmail - can Luân consent Gmail OAuth 1 lan (giai doan 2). Chua port phan doc mail."},
        "boards": {"status": "INIT", "last_check": None, "detail": "",
                   "superteam_seen": [], "raptorx": {},
                   "taskmarket_seen": [], "hyrve_seen": [], "hyrve_total": 0,
                   "frantic_seen": [], "frantic": {}, "all_error_streak": 0,
                   "all_error_alerted": False, "sub_errors": {}},
        "seller_inbox": {"status": "CHO-CONSENT", "last_check": None,
                         "detail": "Phu thuoc Gmail OAuth (chua consent) - khong port phan doc mail; cho Luân consent 1 lan (giai doan 2)."},
    }

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                st = json.load(f)
            d = default_state()
            for k, v in d.items():
                if k not in st:
                    st[k] = v
                elif isinstance(v, dict):
                    for kk, vv in v.items():
                        st[k].setdefault(kk, vv)
            return st
        except Exception as e:
            log("Doc state loi (%s) - dung state mac dinh" % e)
    return default_state()

def save_state(st):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_PATH)

# ================================================================== SYNMERCO
SYN_BASE = "https://synmerco-escrow.onrender.com"
MY_DID = "did:pkh:eip155:8453:" + METAMASK_BASE
SYN_REGISTER_BODY = {
    "displayName": "PepperResearch",
    "description": "Human-supervised AI research agent. Market research, competitor analysis, technical tutorials, case studies. Original, verifiable work only.",
    "doorbellUrl": "https://synmerco-doorbell.pepperresearch.workers.dev",
}
SYN_OK_TYPES = ["research", "writing", "code_review", "code-review", "code review",
                "data", "tutorial", "content"]
SYN_BAD_TYPES = ["referral", "recruit", "shill", "betting", "gambling",
                 "prediction", "captcha", "stake", "engagement"]

def syn_headers(key):
    return {"Authorization": "Bearer " + key}

def syn_bid_message(intent):
    title = (intent.get("title") or intent.get("name") or "the task").strip()
    return ("PepperResearch will deliver exactly what this task asks: " + title +
            ". Original, verifiable work - every figure traced to a named public "
            "source, delivered in the requested format, ready to use without "
            "further cleanup.")

def syn_classify(intent):
    """Tra (verdict, reason): clean / reject / pending."""
    text = " ".join(str(intent.get(k) or "") for k in
                    ("title", "name", "description", "capability", "type", "category")).lower()
    hits = dirty_hits(text)
    if hits:
        return "reject", "dirty: " + ", ".join(hits)
    if "agents already paid only" in text:
        return "reject", "agents-already-paid-only"
    for b in SYN_BAD_TYPES:
        if b in text:
            return "reject", "bad-type: " + b
    for ok in SYN_OK_TYPES:
        if ok in text:
            return "clean", ok
    return "pending", "khong nhan dien duoc loai viec"

def syn_price_competitive(budget_cents, intent):
    """GIA CANH TRANH (Luan chot 07:13 12/11/2026 - thay luat gia that v69
    chot 05:31 cung ngay): sau chuoi bid thua lien tiep (ke ca bid 3860 o
    90% ngan sach), Luan ha mat bang gia de tang cua thang. Mac dinh 60%
    ngan sach (gop truoc phi 3.25%, rong ~58.05%); dai tu quyet 50-70%
    chi ap dung o luot Muse co can cu cu the - duong Actions tu dong
    nay luon dung mac dinh 60%. Vong lap ha gia van BO: bid da nop giu
    nguyen toi khi intent chot. Tra (price, pct)."""
    price = budget_cents * 60 // 100
    return price, 60

def syn_lowest_rival(detail, my_did=MY_DID):
    tops = detail.get("topBids") or detail.get("top_bids") or []
    vals = []
    for b in tops:
        if not isinstance(b, dict):
            continue
        if (b.get("bidderDid") or b.get("bidder_did") or "") == my_did:
            continue
        amt = b.get("amountCents") or b.get("amount_cents") or b.get("amount")
        if isinstance(amt, (int, float)):
            vals.append(int(amt))
    return min(vals) if vals else None

def syn_post_bid(key, intent_id, amount, message):
    return http_curl("POST", "%s/v1/intents/%s/bids" % (SYN_BASE, intent_id),
                     syn_headers(key),
                     {"bidderDid": MY_DID, "amountCents": int(amount), "message": message})

def syn_add_capability_and_rebid(key, intent, amount, message, missing_cap):
    """Uy quyen dung them capability (Luan duyet 02/11): chi khi capability
    mo ta dung viec agent lam duoc (keo sach research/data/writing)."""
    st, d = http_curl("GET", SYN_BASE + "/v1/agents/search?capability=research", syn_headers(key))
    agents = []
    if isinstance(d, dict):
        agents = d.get("agents") or d.get("data") or []
    elif isinstance(d, list):
        agents = d
    mine = None
    for a in agents:
        if isinstance(a, dict) and (a.get("agentDid") or a.get("did")) == MY_DID:
            mine = a
            break
    if not mine:
        return False, "khong tim thay profile cua minh trong agents/search"
    caps = list(mine.get("capabilities") or [])
    if missing_cap not in caps:
        caps.append(missing_cap)
    body = dict(SYN_REGISTER_BODY)
    body["capabilities"] = caps
    st, d = http_curl("POST", SYN_BASE + "/v1/agents/register", syn_headers(key), body)
    if st not in (200, 201):
        return False, "register loi HTTP %s" % st
    st, d = http_curl("GET", SYN_BASE + "/v1/agents/%s/readiness" % urllib.parse.quote(MY_DID, safe=""), syn_headers(key))
    ready = isinstance(d, dict) and (d.get("live") is True or (d.get("data") or {}).get("live") is True)
    if not ready:
        return False, "readiness chua LIVE sau khi them capability"
    st, d = syn_post_bid(key, intent.get("intentId") or intent.get("id"), amount, message)
    if st in (200, 201):
        return True, (d or {}).get("bidId") or (d or {}).get("id") or ""
    return False, "bid lai loi HTTP %s" % st

def watch_synmerco(st, alerts):
    w = st["synmerco"]
    w["last_check"] = iso_vn()
    key = (os.environ.get("SYNMERCO_API_KEY") or "").strip()
    if not key:
        w["status"] = "CHO-CREDENTIAL"
        w["detail"] = "Chua co secret SYNMERCO_API_KEY - chua doc duoc bang Synmerco (heartbeat/intents deu can key)."
        return
    # heartbeat + readiness
    http_curl("POST", SYN_BASE + "/v1/agents/heartbeat", syn_headers(key), {"availability": "online"})
    stc, rd = http_curl("GET", SYN_BASE + "/v1/agents/%s/readiness" % urllib.parse.quote(MY_DID, safe=""), syn_headers(key))
    rdata = rd if isinstance(rd, dict) else {}
    if isinstance(rdata.get("data"), dict):
        rdata = rdata["data"]
    live = rdata.get("live")
    missing = rdata.get("missing") or []
    if stc == 200 and (live is False or missing):
        if not w.get("readiness_alerted"):
            alerts.append("[Synmerco] SU CO READINESS: live=%s missing=%s" % (live, missing))
            w["readiness_alerted"] = True
    elif stc == 200:
        w["readiness_alerted"] = False
    # intents open
    stc, d = http_curl("GET", SYN_BASE + "/v1/intents?status=open", syn_headers(key))
    if stc != 200 or d is None:
        w["status"] = "LOI"
        w["detail"] = "GET intents loi HTTP %s" % stc
        return
    intents = d.get("intents") if isinstance(d, dict) else d
    if not isinstance(intents, list):
        intents = (d.get("data") or []) if isinstance(d, dict) else []
    seen = set(w.get("seen_ids") or [])
    open_ids = set()
    new_clean = 0
    for intent in intents:
        if not isinstance(intent, dict):
            continue
        iid = intent.get("intentId") or intent.get("id")
        if not iid:
            continue
        open_ids.add(iid)
        if iid in seen:
            continue
        seen.add(iid)
        # intent moi: doc chi tiet roi xet cong
        std, det = http_curl("GET", SYN_BASE + "/v1/intents/" + iid, syn_headers(key))
        full = det if isinstance(det, dict) and std == 200 else intent
        if isinstance(full.get("data"), dict):
            full = full["data"]
        verdict, why = syn_classify(full)
        title = (full.get("title") or full.get("name") or iid)[:110]
        budget = full.get("budgetCents") or full.get("budget_cents") or intent.get("budgetCents")
        budget = int(budget) if isinstance(budget, (int, float)) else None
        if verdict == "reject":
            log("Synmerco: loai intent %s (%s)" % (iid, why))
            continue
        if verdict == "pending" or not budget:
            w["pending"][iid] = {"reported_at": time.time(), "title": title,
                                 "budget_cents": budget, "reason": why}
            alerts.append("[Synmerco] KEO MOI CHUA PHAN LOAI CHAC - cho duyet tay:\n%s\nNgan sach: %s | Ly do: %s\nLink: %s/v1/intents/%s"
                          % (title, ("$%.2f" % (budget / 100)) if budget else "?", why, SYN_BASE, iid))
            continue
        # SACH -> bid ngay theo luat gia
        msg = syn_bid_message(full)
        price, level = syn_price_competitive(budget, full)
        basis = "bid %d%% ngan sach theo luat gia canh tranh (Luan chot 07:13 12/11) - mac dinh 60%%, dai tu quyet 50-70%%; khong sua gia bid da nop" % level
        if price < 100:
            if budget > 100:
                price = 100
                basis += "; gia tinh < san -> bid san $1.00"
            else:
                w["pending"][iid] = {"reported_at": time.time(), "title": title,
                                     "budget_cents": budget, "reason": "ngan sach <= $1"}
                alerts.append("[Synmerco] KEO SACH NHUNG NGAN SACH QUA NHO ($%.2f) - khong bid, cho duyet: %s" % (budget / 100, title))
                continue
        if price >= budget:
            price = budget - 1
        stb, db = syn_post_bid(key, iid, price, msg)
        if stb == 412:
            cap = full.get("capability") or ""
            ok, info = (False, "thieu capability khong ro ten")
            if cap and syn_classify(full)[0] == "clean":
                ok, info = syn_add_capability_and_rebid(key, full, price, msg, cap)
            if ok:
                w["my_bids"][iid] = {"amount_cents": price, "bid_id": info, "message": msg,
                                     "title": title, "budget_cents": budget, "history": [price]}
                alerts.append("[Synmerco] DA TU BID (da tu them capability '%s' theo uy quyen 02/11):\n%s\nBid: $%.2f | bidId: %s | Can cu gia: %s | Rong sau phi 3.25%%: ~$%.2f\nLuu y: jobLock chi fund 1 escrow/luc - thang that chi fund sau khi escrow cu settle."
                              % (cap, title, price / 100, info, basis, price / 100 * 0.9675))
                new_clean += 1
            else:
                alerts.append("[Synmerco] BID LOI 412 cho keo sach '%s': %s - can Luân/main xem." % (title, info))
            continue
        if stb in (200, 201):
            bid_id = (db or {}).get("bidId") or (db or {}).get("id") or ""
            w["my_bids"][iid] = {"amount_cents": price, "bid_id": bid_id, "message": msg,
                                 "title": title, "budget_cents": budget, "history": [price]}
            alerts.append("[Synmerco] DA TU BID NGAY (luat Luan duyet 01/11):\n%s\nBid: $%.2f | bidId: %s | Can cu gia: %s | Rong sau phi 3.25%%: ~$%.2f\nLuu y: jobLock chi fund 1 escrow/luc - thang that chi fund sau khi escrow cu settle."
                          % (title, price / 100, bid_id, basis, price / 100 * 0.9675))
            new_clean += 1
        else:
            alerts.append("[Synmerco] BID LOI HTTP %s cho keo sach '%s' - ghi nhan, khong thu lai cung luot." % (stb, title))
    w["seen_ids"] = sorted(seen)
    # pending qua han 30 phut (luat 5c): tu bid bang gia nhap
    for iid, p in list(w.get("pending", {}).items()):
        if time.time() - float(p.get("reported_at") or 0) < 1800:
            continue
        std, det = http_curl("GET", SYN_BASE + "/v1/intents/" + iid, syn_headers(key))
        if std != 200 or not isinstance(det, dict):
            continue
        full = det.get("data") if isinstance(det.get("data"), dict) else det
        if (full.get("status") or "open") != "open":
            del w["pending"][iid]
            continue
        budget = p.get("budget_cents")
        if not budget:
            continue
        price, level = syn_price_competitive(int(budget), full)
        if price < 100 or price >= int(budget):
            continue
        msg = syn_bid_message(full)
        stb, db = syn_post_bid(key, iid, price, msg)
        if stb in (200, 201):
            bid_id = (db or {}).get("bidId") or (db or {}).get("id") or ""
            w["my_bids"][iid] = {"amount_cents": price, "bid_id": bid_id, "message": msg,
                                 "title": p.get("title"), "budget_cents": budget, "history": [price]}
            alerts.append("[Synmerco] TU BID THEO LUAT QUA HAN 30 PHUT (Luan duyet 27/10): %s - $%.2f (bidId %s)" % (p.get("title"), price / 100, bid_id))
            del w["pending"][iid]
    # theo doi bid cua minh: thang/thua (gia giu nguyen - khong con vong lap ha gia)
    for iid, b in list(w.get("my_bids", {}).items()):
        std, det = http_curl("GET", SYN_BASE + "/v1/intents/" + iid, syn_headers(key))
        if std != 200 or not isinstance(det, dict):
            continue
        full = det.get("data") if isinstance(det.get("data"), dict) else det
        status = (full.get("status") or "").lower()
        winner = None
        for f in ("matchedAgentDid", "awardedAgentDid", "winnerDid", "matchedTo", "awardedTo"):
            if full.get(f):
                winner = full.get(f)
                break
        if status in ("matched", "awarded", "funded"):
            if winner == MY_DID or (winner is None and status in ("awarded", "funded")):
                alerts.append("[Synmerco] THANG THAU: %s - bid $%.2f. Main agent can bat dau lam bai giao hang ngay." % (b.get("title"), (b.get("amount_cents") or 0) / 100))
            else:
                log("Synmerco: bid thua (matched cho agent khac): %s" % iid)
            del w["my_bids"][iid]
            continue
        if status in ("closed", "expired", "cancelled", "canceled"):
            del w["my_bids"][iid]
            continue
        # Vong lap ha gia DA BO (Luan chot 12/11 theo v69): bid gia that,
        # giu nguyen gia da nop cho toi khi intent matched/dong/het han.
    # intent dang giu hang (vd bid 2590 - escrow funded cho giao bai)
    for iid, info in list(w.get("watch_ids", {}).items()):
        std, det = http_curl("GET", SYN_BASE + "/v1/intents/" + iid, syn_headers(key))
        if std != 200 or not isinstance(det, dict):
            continue
        full = det.get("data") if isinstance(det.get("data"), dict) else det
        cur = (full.get("status") or "").lower()
        if cur and cur != (info.get("status") or "").lower():
            alerts.append("[Synmerco] Intent dang theo doi %s doi trang thai: %s -> %s (%s)" % (iid, info.get("status"), cur, info.get("title", "")))
            info["status"] = cur
    w["status"] = "LIVE"
    w["detail"] = "Dang canh %d intent mo, %d bid cua minh dang mo, %d cho duyet. Readiness %s." % (
        len(open_ids), len(w.get("my_bids", {})), len(w.get("pending", {})), "LIVE" if live else "?")

# ================================================================== CC0
CC0_KV_TITLE = "cc0-jobs"
CC0_SYNC_GRACE = 180

def cc0_kv_get(token, ns_id, key):
    url = "https://api.cloudflare.com/client/v4/accounts/%s/storage/kv/namespaces/%s/values/%s" % (
        CC0_ACCOUNT_ID, ns_id, urllib.parse.quote(key, safe=""))
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""

def watch_cc0(st, alerts):
    w = st["cc0"]
    w["last_check"] = iso_vn()
    token = (os.environ.get("CC0_CF_API_TOKEN") or "").strip()
    if not token:
        w["status"] = "CHO-CREDENTIAL"
        w["detail"] = "Chua co secret CC0_CF_API_TOKEN (token Cloudflare doc KV cc0-jobs, account cua Luân) - chua doc duoc don CC0."
        return
    if not w.get("kv_namespace_id"):
        stc, d = http_json("GET", "https://api.cloudflare.com/client/v4/accounts/%s/storage/kv/namespaces?per_page=50" % CC0_ACCOUNT_ID,
                           {"Authorization": "Bearer " + token})
        found = None
        for ns in ((d or {}).get("result") or []):
            if ns.get("title") == CC0_KV_TITLE:
                found = ns.get("id")
                break
        if not found:
            w["status"] = "LOI"
            w["detail"] = "Khong tim thay KV namespace '%s' (HTTP %s) - token thieu quyen doc KV?" % (CC0_KV_TITLE, stc)
            return
        w["kv_namespace_id"] = found
    ns_id = w["kv_namespace_id"]
    stc, raw = cc0_kv_get(token, ns_id, "meta:recent_job_ids")
    if stc == 404:
        w["status"] = "LIVE"
        w["detail"] = "KV chua co index (chua job nao toi ke tu khi Worker deploy). 0 don."
        return
    if stc != 200:
        w["status"] = "LOI"
        w["detail"] = "Doc meta:recent_job_ids loi HTTP %s" % stc
        return
    try:
        recent = json.loads(raw)
    except Exception:
        recent = []
    _, last_id = cc0_kv_get(token, ns_id, "meta:last_job_id")
    _, last_at = cc0_kv_get(token, ns_id, "meta:last_job_at")
    last_id = (last_id or "").strip()
    # tripwire coverage: job moi nhat chua nam trong index
    if last_id and last_id not in recent:
        age = None
        try:
            dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - dt).total_seconds()
        except Exception:
            pass
        if age is not None and age > CC0_SYNC_GRACE and w.get("coverage_alerted_for") != last_id:
            alerts.append("[CC0] CANH BAO COVERAGE: job %s da toi luc %s nhung index meta:recent_job_ids chua phu (KV list khong dung duoc) - can doi chieu tay bang cc0.py me-jobs." % (last_id, last_at))
            w["coverage_alerted_for"] = last_id
    new_paid, new_test, pending_total = 0, 0, 0
    for jid in recent[:50]:
        stc, raw = cc0_kv_get(token, ns_id, "job:" + jid)
        if stc != 200:
            continue
        try:
            job = json.loads(raw)
        except Exception:
            continue
        if job.get("status") != "pending":
            continue
        pending_total += 1
        inp = job.get("input") or {}
        topic = inp.get("topic") or inp.get("question") or str(inp)[:120]
        if job.get("is_test"):
            if jid not in w["reported_test"]:
                w["reported_test"].append(jid)
                new_test += 1
                alerts.append("[CC0] PROBE (test, khong tien) - job %s: %s | received %s. Probe cung can callback brief that moi giu listing active." % (jid, topic, job.get("received_at")))
        else:
            if jid not in w["reported_paid"]:
                w["reported_paid"].append(jid)
                new_paid += 1
                alerts.append("[CC0] DON PAID MOI 1.00 USDC: job %s\nInput: %s\nReceived: %s\nKHAN: cc0 tu refund neu khong callback trong 10 phut ke tu received_at - main agent can lam brief + fulfill ngay (fulfill o phase Worker/main, watch chi bao)."
                              % (jid, json.dumps(inp, ensure_ascii=False)[:500], job.get("received_at")))
    w["reported_paid"] = w["reported_paid"][-100:]
    w["reported_test"] = w["reported_test"][-100:]
    w["status"] = "LIVE"
    w["detail"] = "Index %d job gan nhat; %d pending; moi vong nay: %d paid, %d probe. Sweep/fulfill: phase 2 (Worker CC0), watch chi doc + bao." % (
        len(recent), pending_total, new_paid, new_test)

# ================================================================== MOLTJOBS
MOLT_BASE = "https://api.moltjobs.io"
MOLT_AGENT = "pepperresearch"
MOLT_AGENT_ID = "70e9d11a-b795-4a62-8403-0d0d24e36f28"
MOLT_BASELINE_SETTLED = 42.30
MOLT_BASELINE_EMPLOYERS = 1

def molt_gate(job):
    purpose = (job.get("purpose") or "").upper()
    if purpose == "PLATFORM_REFERRAL":
        return False, "referral"
    text = " ".join(str(job.get(k) or "") for k in ("title", "name", "description", "purpose", "category", "vertical")).lower()
    hits = dirty_hits(text)
    if hits:
        return False, "dirty: " + ", ".join(hits)
    budget = parse_money(job.get("budgetUsdc") if job.get("budgetUsdc") is not None else
                         job.get("budget") if job.get("budget") is not None else job.get("amountUsdc"))
    if budget is None or budget < 2:
        return False, "ngan sach < $2 hoac khong ro"
    cat = " ".join(str(job.get(k) or "") for k in ("category", "vertical", "type")).lower()
    if not any(k in (cat + " " + text) for k in ("research", "writing", "data", "code")):
        return False, "ngoai pham vi research/writing/data/code_review"
    return True, "ok"

def watch_moltjobs(st, alerts):
    w = st["moltjobs"]
    w["last_check"] = iso_vn()
    key = (os.environ.get("MOLTJOBS_API_KEY") or "").strip()
    # --- stats public: luon chay, ke ca chua co key
    stats_note = ""
    stc, d = http_json("GET", MOLT_BASE + "/v1/stats")
    if stc == 200 and isinstance(d, dict):
        data = d.get("data") or d
        mkt = data.get("marketplace") or data
        settled = mkt.get("settledVolumeUsdc")
        employers = mkt.get("fundedEmployers")
        ms = w["stats_milestone"]
        if ms.get("settled") is None:
            ms["settled"] = MOLT_BASELINE_SETTLED
            ms["funded_employers"] = MOLT_BASELINE_EMPLOYERS
        if isinstance(settled, (int, float)) and settled > float(ms["settled"]):
            alerts.append("[MoltJobs] TIN HIEU SAN CO TIEN THAT MOI: settledVolumeUsdc %.2f -> %.2f (fundedEmployers %s). Moc cu: 42.30/1." % (float(ms["settled"]), settled, employers))
            ms["settled"] = settled
        if isinstance(employers, (int, float)) and employers > int(ms["funded_employers"] or 0):
            if not (isinstance(settled, (int, float)) and settled > MOLT_BASELINE_SETTLED):
                alerts.append("[MoltJobs] fundedEmployers tang len %s (moc cu 1) - tin hieu san co tien that moi." % employers)
            ms["funded_employers"] = employers
        stats_note = "Stats: settled $%s, fundedEmployers %s." % (settled, employers)
    if not key:
        w["status"] = "CHO-CREDENTIAL"
        w["detail"] = "Chua co secret MOLTJOBS_API_KEY - heartbeat/jobs chua chay. " + stats_note
        return
    hdr = {"Authorization": "Bearer " + key}
    # heartbeat PHAI gui KHONG body (co body agentId -> 400, da kiem chung)
    stc, hb = http_curl("POST", MOLT_BASE + "/v1/agents/heartbeat", hdr, None)
    assignments = []
    if isinstance(hb, dict):
        assignments = ((hb.get("data") or {}).get("assignments") or hb.get("assignments") or [])
    stc2, ag = http_json("GET", MOLT_BASE + "/v1/agents/" + MOLT_AGENT, hdr)
    agent_status = None
    if isinstance(ag, dict):
        agent_status = (ag.get("data") or ag).get("status")
    if agent_status:
        prev = w.get("agent_status")
        w["agent_status"] = agent_status
        if agent_status != "ACTIVE" and prev != agent_status:
            alerts.append("[MoltJobs] SU CO: trang thai agent = %s (khac ACTIVE)." % agent_status)
    for a in assignments:
        aid = a.get("jobId") or a.get("id") if isinstance(a, dict) else None
        if aid and aid not in w["seen_assignments"]:
            w["seen_assignments"].append(aid)
            title = a.get("title") or a.get("jobTitle") or aid
            if is_night_vn():
                stc3, _ = http_json("PATCH", MOLT_BASE + "/v1/jobs/%s/start" % aid, hdr, {})
                alerts.append("[MoltJobs] ASSIGNMENT MOI (khung dem - da PATCH start %s): %s. Deliverable can Gemini/main xu ly tiep - da ghi state." % (stc3, title))
            else:
                alerts.append("[MoltJobs] ASSIGNMENT MOI: %s - main agent xu ly ngay." % title)
    # jobs open
    stc, d = http_json("GET", MOLT_BASE + "/v1/jobs?status=OPEN", hdr)
    jobs = []
    if isinstance(d, dict):
        jobs = d.get("data") or d.get("jobs") or []
    elif isinstance(d, list):
        jobs = d
    seen = set(w.get("seen_job_ids") or [])
    month = now_vn().strftime("%Y-%m")
    ledger = w.setdefault("bid_ledger", {})
    used = int(ledger.get(month, 0))
    new_clean = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        jid = job.get("id") or job.get("jobId")
        if not jid or jid in seen:
            continue
        seen.add(jid)
        ok, why = molt_gate(job)
        if not ok:
            log("MoltJobs: loai job %s (%s)" % (jid, why))
            continue
        # kiem chung funded bang GET chi tiet (list tung nhap nho funded)
        stc3, det = http_json("GET", MOLT_BASE + "/v1/jobs/" + jid, hdr)
        full = (det.get("data") or det) if isinstance(det, dict) else {}
        if full.get("funded") is not True:
            log("MoltJobs: job %s chua funded that (detail funded=%s) - bo qua" % (jid, full.get("funded")))
            continue
        budget = parse_money(full.get("budgetUsdc") if full.get("budgetUsdc") is not None else full.get("budget"))
        title = full.get("title") or job.get("title") or jid
        deadline = full.get("deadline") or full.get("deadlineAt") or "?"
        if is_night_vn() and used < 10:
            cover = ("PepperResearch will deliver exactly what this job requires: %s. "
                     "Original, verifiable work with sources cited, in the required output schema." % title)
            stb, db = http_json("POST", MOLT_BASE + "/v1/jobs/%s/bids" % jid, hdr,
                                {"agentId": MOLT_AGENT, "proposedUsdc": budget, "coverLetter": cover})
            if stb in (200, 201):
                used += 1
                ledger[month] = used
                alerts.append("[MoltJobs] TU BID KHUNG DEM: %s - $%s (bid free thang nay: %d/10). Cho assignment de lam deliverable." % (title, budget, used))
                new_clean += 1
            elif stb == 409:
                log("MoltJobs: bid 409 (trung/het credit) job %s - khong thu lai" % jid)
            else:
                alerts.append("[MoltJobs] Bid loi HTTP %s cho job sach '%s'." % (stb, title))
        else:
            alerts.append("[MoltJobs] JOB SACH MOI (funded that): %s\nNgan sach: $%s | Han: %s | Link: https://moltjobs.io/jobs/%s\nDat cong: escrow funded kiem chung qua API, trong pham vi research/writing/data. Bid do main agent xu (hoac tu bid trong khung dem 21:00-06:00)." % (title, budget, deadline, jid))
            new_clean += 1
    w["seen_job_ids"] = sorted(seen)[-500:]
    w["status"] = "LIVE"
    w["detail"] = "Agent %s; %d job mo; bid free thang %s: %d/10. %s" % (w.get("agent_status"), len(jobs), month, used, stats_note)

# ================================================================== OWOCKIBOT
OWO_BASE = "https://bounty.owockibot.xyz"
OWO_OK_TAGS = ["writing", "research", "data", "code", "review", "content",
               "analysis", "documentation", "translation", "article", "report"]
OWO_DIRTY = ["shill", "fake", "betting", "gambl", "prediction", "doxx", "doxing",
             "mule", "launder", "impersonat", "spam", "captcha", "casino",
             "airdrop farming", "sybil", "engagement farm"]

def owo_usdc(raw):
    try:
        return int(raw) / 1_000_000
    except Exception:
        return None

def watch_owockibot(st, alerts):
    w = st["owockibot"]
    w["last_check"] = iso_vn()
    stc, d = http_json("GET", OWO_BASE + "/discover")
    if stc != 200 or not isinstance(d, dict):
        w["status"] = "LOI"
        w["detail"] = "GET /discover loi HTTP %s" % stc
        return
    bounties = d.get("bounties") or []
    seen = w.setdefault("seen", {})
    # trang thai claim cua minh theo server
    stc_m, all_b = http_json("GET", OWO_BASE + "/bounties")
    mine = []
    if stc_m == 200 and isinstance(all_b, list):
        mine = [b for b in all_b if (b.get("claimedBy") or "").lower() == METAMASK_BASE.lower()]
    active_server = None
    for b in mine:
        if b.get("status") == "claimed":
            active_server = b
    ac = w.get("active_claim")
    if ac and not any(str(b.get("id")) == str(ac.get("id")) and b.get("status") == "claimed" for b in mine):
        # claim cua minh da chuyen trang thai (submitted/completed/het)
        done = next((b for b in mine if str(b.get("id")) == str(ac.get("id"))), None)
        if done:
            alerts.append("[Owockibot] Claim '%s' doi trang thai tren server: %s (tx: %s)." % (ac.get("title"), done.get("status"), done.get("txHash") or done.get("paymentTx") or "chua co"))
        w["active_claim"] = None
        ac = None
    if active_server and not ac:
        ac = {"id": str(active_server.get("id")), "title": active_server.get("title"),
              "reward_usdc": owo_usdc(active_server.get("reward")), "status": "claimed",
              "note": "phat hien tu server (claim tu phia Muse hoac truoc do)"}
        w["active_claim"] = ac
    new_n = 0
    for b in bounties:
        bid = str(b.get("id"))
        if bid in seen:
            continue
        seen[bid] = {"title": b.get("title"), "first_seen": iso_vn()}
        new_n += 1
        stc2, det = http_json("GET", OWO_BASE + "/bounties/" + bid)
        full = det if isinstance(det, dict) and stc2 == 200 else b
        text = " ".join(str(full.get(k) or "") for k in ("title", "description", "requirements")).lower()
        tags = " ".join(full.get("tags") or []).lower()
        reward = owo_usdc(full.get("reward"))
        dl_ms = full.get("deadline")
        hours_left = None
        if isinstance(dl_ms, (int, float)):
            hours_left = (dl_ms - time.time() * 1000) / 3600000
        title = full.get("title") or bid
        # cong sach cung
        dirty = [k for k in OWO_DIRTY if k in (text + " " + tags)]
        if dirty:
            seen[bid]["verdict"] = "reject-dirty:" + ",".join(dirty)
            continue
        in_scope = any(k in tags or k in text for k in OWO_OK_TAGS)
        # dieu kien (b): thuong USDC Base - board mac dinh dung; neu field
        # token/chain chi khac thi rot
        token_bad = False
        for f in ("token", "chain", "network", "currency"):
            v = str(full.get(f) or "").lower()
            if v and v not in ("usdc", "base", "usdc-base", "8453"):
                token_bad = True
        deadline_ok = (hours_left is not None and hours_left >= 24) or \
                      (reward is not None and reward <= 10 and hours_left is not None and hours_left >= 4)
        borderline = []
        if not in_scope:
            borderline.append("loai viec chua ro trong pham vi")
        if token_bad:
            borderline.append("thuong khong phai USDC Base")
        if not deadline_ok:
            borderline.append("deadline < 24h")
        if reward is None:
            borderline.append("khong doc duoc so thuong")
        if w.get("active_claim"):
            seen[bid]["verdict"] = "queued-dang-giu-claim-khac"
            if bid not in w["queued"]:
                w["queued"].append(bid)
            continue
        if borderline:
            seen[bid]["verdict"] = "borderline"
            alerts.append("[Owockibot] Bounty moi LUONG CHUNG - cho Luan quyet:\n%s\nThuong: %s USDC | Deadline con: %s gio\nChua dat/chua ro: %s\nLink: %s/bounties/%s"
                          % (title, reward, ("%.0f" % hours_left) if hours_left is not None else "?",
                             "; ".join(borderline), OWO_BASE, bid))
            continue
        # CLAIM NGAY (luat Luan duyet 27/10)
        stc3, res = http_json("POST", OWO_BASE + "/bounties/%s/claim" % bid, None, {"address": METAMASK_BASE})
        if stc3 != 200:
            # ket qua khong ro -> kiem chung bang server truoc khi bao
            stc4, chk = http_json("GET", OWO_BASE + "/bounties/" + bid)
            claimed_by = (chk or {}).get("claimedBy") if isinstance(chk, dict) else None
            if (claimed_by or "").lower() != METAMASK_BASE.lower():
                alerts.append("[Owockibot] CLAIM LOI HTTP %s cho bounty '%s' - chua claim duoc, can kiem tra." % (stc3, title))
                continue
        rec = {"id": bid, "title": title, "reward_usdc": reward, "tags": full.get("tags"),
               "deadline_ms": dl_ms, "claimed_at": iso_vn(), "status": "claimed"}
        w["active_claim"] = rec
        w.setdefault("claims", []).append(rec)
        seen[bid]["verdict"] = "claimed"
        net = reward * 0.95 if reward is not None else None
        alerts.append("[Owockibot] DA TU CLAIM theo luat Luan duyet 27/10:\n%s\nThuong: %s USDC (rong sau phi 5%%: ~%s USDC) - ve thang MetaMask cua Luan (Base)\nDeadline: %s\nViec can giao: %s\nLuu y: submit sau claim toi thieu 10 phut, do main agent/Gemini lam bai."
                      % (title, reward, ("%.2f" % net) if net is not None else "?",
                         datetime.fromtimestamp(dl_ms / 1000, VN).strftime("%d/%m %H:%M") if dl_ms else "?",
                         (full.get("requirements") or full.get("description") or "")[:300]))
    w["status"] = "LIVE"
    w["detail"] = "%d bounty dang mo; moi vong nay: %d; claim dang giu: %s." % (
        d.get("count", len(bounties)), new_n, (w["active_claim"] or {}).get("title") or "khong")

# ================================================================== FIVERR
def watch_fiverr(st, alerts):
    w = st["fiverr"]
    w["last_check"] = iso_vn()
    if (os.environ.get("GMAIL_REFRESH_TOKEN") or "").strip():
        w["status"] = "CHO-CONSENT"
        w["detail"] = "Da thay GMAIL_REFRESH_TOKEN nhung phan doc Gmail chua port trong ban nay - can xac minh co che truoc khi bat."
    else:
        w["status"] = "CHO-CONSENT"
        w["detail"] = "Ban goc doc hoat dong Fiverr qua Gmail (mail thong bao seller) - can Luân consent Gmail OAuth 1 lan (giai doan 2). Chua port phan doc mail."

# ================================================================== BOARDS
RAPTORX_LISTING_ID = "0b31b391-94f2-4021-bf78-f2b1b7a9c83d"
RAPTORX_SUBMISSION_ID = "0f855d10-cbbb-4a17-862b-dc9efd9b38a5"

def boards_gate_superteam(lst):
    title = (lst.get("title") or "")
    hits = dirty_hits(title + " " + (lst.get("description") or ""))
    if hits:
        return False, "dirty: " + ", ".join(hits)
    reward = parse_money(lst.get("rewardAmount"))
    subs = ((lst.get("_count") or {}).get("Submission"))
    if reward is None:
        return False, "khong ro giai"
    if reward < 5:
        return False, "giai dust < $5"
    if isinstance(subs, (int, float)) and subs > 100 and reward < 50:
        return False, "qua dong bai nop cho giai nho (winner-take-all)"
    return True, "ok"

def watch_boards(st, alerts):
    w = st["boards"]
    w["last_check"] = iso_vn()
    errs = {}
    # --- Superteam: take=10 cho listing moi; take=100&status=all cho RaptorX
    st_new_ids = []
    stc, d = http_curl("GET", "https://earn.superteam.fun/api/listings/?take=10")
    items = []
    if isinstance(d, list):
        items = d
    elif isinstance(d, dict):
        items = d.get("data") or d.get("listings") or []
    if stc != 200:
        errs["superteam"] = "HTTP %s" % stc
    if items:
        seen = set(w.get("superteam_seen") or [])
        for lst in items:
            lid = lst.get("id")
            if not lid:
                continue
            if lid not in seen:
                seen.add(lid)
                st_new_ids.append(lid)
                ok, why = boards_gate_superteam(lst)
                if ok:
                    alerts.append("[Boards/Superteam] KEO MOI QUA CONG SACH:\n%s\nGiai: %s %s | Han: %s | Link: https://earn.superteam.fun/listings/%s\nLy do dat cong: poster khoa giai tren Superteam (escrow nen tang), trong pham vi lam duoc, khong dau hieu tien ban."
                                  % (lst.get("title"), lst.get("rewardAmount"), lst.get("token") or "", lst.get("deadline"), lst.get("slug") or lid))
                else:
                    log("Boards/Superteam: listing moi %s rot cong (%s)" % (lid, why))
        w["superteam_seen"] = sorted(seen)
    # RaptorX
    stc2, d2 = http_curl("GET", "https://earn.superteam.fun/api/listings/?take=100&status=all", timeout=90)
    items2 = []
    if isinstance(d2, list):
        items2 = d2
    elif isinstance(d2, dict):
        items2 = d2.get("data") or d2.get("listings") or []
    rx = next((x for x in items2 if x.get("id") == RAPTORX_LISTING_ID), None)
    if rx is not None:
        cur = {"isWinnersAnnounced": rx.get("isWinnersAnnounced"),
               "winnersAnnouncedAt": rx.get("winnersAnnouncedAt"),
               "submissions": (rx.get("_count") or {}).get("Submission"),
               "status": rx.get("status")}
        prev = w.get("raptorx") or {}
        if prev.get("isWinnersAnnounced") is not True and cur["isWinnersAnnounced"] is True:
            winners_raw = json.dumps(rx.get("winners") or rx.get("Winners") or "")
            if RAPTORX_SUBMISSION_ID in winners_raw:
                alerts.append("[Boards/Superteam] RAPTORX DA CONG BO - SUBMISSION CUA MINH CO TRONG DANH SACH WINNERS! Kiem chung ngay tren Superteam (giai 75/50 USDC, cong bo truoc 15/11).")
            elif winners_raw and winners_raw != "[]":
                alerts.append("[Boards/Superteam] RaptorX da cong bo winners nhung khong thay submission cua minh (%s) trong danh sach - kha nang cao la thua. Kiem chung lai tren Superteam." % RAPTORX_SUBMISSION_ID)
            else:
                alerts.append("[Boards/Superteam] RaptorX: isWinnersAnnounced=true nhung API chua tra danh sach winners - can kiem chung tay tren Superteam ngay.")
        elif prev and prev.get("status") != cur["status"] and cur["status"]:
            alerts.append("[Boards/Superteam] RaptorX doi trang thai listing: %s -> %s (submissions: %s, winners announced: %s)." % (prev.get("status"), cur["status"], cur["submissions"], cur["isWinnersAnnounced"]))
        w["raptorx"] = cur
    elif stc2 != 200:
        errs["superteam_raptorx"] = "HTTP %s" % stc2
    # --- Taskmarket qua CLI chinh thuc (nhu ban goc)
    try:
        r = subprocess.run(["npx", "-y", "@lucid-agents/taskmarket@1.25.0", "--network", "base", "task", "list"],
                           capture_output=True, text=True, timeout=50)
        out = (r.stdout or "").strip()
        tasks = None
        try:
            parsed = json.loads(out)
            if isinstance(parsed, list):
                tasks = parsed
            elif isinstance(parsed, dict):
                data = parsed.get("data") if isinstance(parsed.get("data"), dict) else parsed
                tasks = data.get("tasks") or []
        except Exception:
            ids = re.findall(r"TSK-[A-Z0-9]+", out)
            tasks = [{"referenceCode": i} for i in dict.fromkeys(ids)]
        if tasks is None:
            errs["taskmarket"] = "khong parse duoc output CLI"
        else:
            seen = set(w.get("taskmarket_seen") or [])
            for t in tasks:
                if not isinstance(t, dict):
                    continue
                tid = t.get("referenceCode") or t.get("id")
                if not tid:
                    continue
                if tid not in seen:
                    seen.add(tid)
                    raw_reward = t.get("netReward") if t.get("netReward") is not None else t.get("reward")
                    amt = None
                    if isinstance(raw_reward, str) and raw_reward.isdigit():
                        amt = int(raw_reward) / 1_000_000
                    else:
                        amt = parse_money(raw_reward)
                    desc = t.get("description") or ""
                    title = (desc.strip().split("\n")[0] or tid)[:110]
                    hits = dirty_hits(desc)
                    stake = bool(t.get("stakeRequired"))
                    if not hits and not stake and amt is not None and amt >= 2 and t.get("escrowTxHash"):
                        alerts.append("[Boards/Taskmarket] TASK MOI QUA CONG:\n%s - $%.2f (task %s, Base, escrow %s, %s bai nop). Kiem tra nhanh truoc khi bid."
                                      % (title, amt, tid, str(t.get("escrowTxHash"))[:14] + "...", t.get("submissionCount")))
                    else:
                        log("Boards/Taskmarket: task moi %s rot cong (amt=%s stake=%s dirty=%s)" % (tid, amt, stake, hits))
            w["taskmarket_seen"] = sorted(seen)
    except Exception as e:
        errs["taskmarket"] = str(e)[:100]
    # --- HYRVE
    stc3, d3 = http_json("GET", "https://api.hyrveai.com/v1/jobs")
    if stc3 == 200 and isinstance(d3, dict):
        jobs = d3.get("jobs") or []
        total = (d3.get("pagination") or {}).get("total", len(jobs))
        seen = set(w.get("hyrve_seen") or [])
        for j in jobs:
            jid = str(j.get("id") or j.get("jobId") or "")
            if not jid:
                continue
            if jid not in seen:
                seen.add(jid)
                title = j.get("title") or j.get("name") or jid
                amt = parse_money(j.get("budget") if j.get("budget") is not None else j.get("amount") if j.get("amount") is not None else j.get("pay"))
                hits = dirty_hits(title + " " + (j.get("description") or ""))
                if not hits and (amt is None or amt >= 2):
                    alerts.append("[Boards/HYRVE] JOB DAU TIEN/MOI TREN HYRVE:\n%s - %s | id %s. San truoc gio total=0 - kiem tra cong sach thu cong tiep." % (title, ("$%s" % amt) if amt else "chua ro ngan sach", jid))
                else:
                    log("Boards/HYRVE: job moi %s rot cong" % jid)
        w["hyrve_seen"] = sorted(seen)
        w["hyrve_total"] = total
    else:
        errs["hyrve"] = "HTTP %s" % stc3
    # --- Frantic
    stc4, d4 = http_json("GET", "https://gofrantic.com/v1/board")
    stc5, d5 = http_json("GET", "https://gofrantic.com/v1/stats")
    if stc4 == 200 and isinstance(d4, dict):
        board = d4.get("board") or {}
        open_b = board.get("open_bounties") or board.get("bounties") or []
        top_claim_state = ((d4.get("actions") or {}).get("claim") or {}).get("state")
        seen = set(w.get("frantic_seen") or [])
        for b in open_b:
            num = b.get("number")
            if num is None:
                continue
            if num not in seen:
                seen.add(num)
                claim_state = ((b.get("actions") or {}).get("claim") or {}).get("state") or top_claim_state
                price = b.get("price_usd")
                if claim_state != "requires_identity" and isinstance(price, (int, float)) and price >= 2 and b.get("funded"):
                    alerts.append("[Boards/Frantic] BOUNTY MOI KHONG CAN VERIFIED IDENTITY >= $2:\n#%s %s - $%s (funded). Link: https://gofrantic.com/bounties/%s" % (num, b.get("title"), price, num))
                else:
                    log("Boards/Frantic: bounty moi #%s (claim=%s price=%s) - chua dat dieu kien bao" % (num, claim_state, price))
        w["frantic_seen"] = sorted(seen)
        w["frantic"] = {"bounties_open": board.get("bounties_open"),
                        "moved_usd": board.get("moved_usd") or (d5 or {}).get("movedUsd"),
                        "funded_usd": board.get("funded_usd")}
    else:
        errs["frantic"] = "HTTP %s" % stc4
    w["sub_errors"] = errs
    if len(errs) >= 4:
        w["all_error_streak"] = int(w.get("all_error_streak") or 0) + 1
        if w["all_error_streak"] >= 3 and not w.get("all_error_alerted"):
            alerts.append("[Boards] CA 4 NGUON LOI 3 LUOT LIEN TIEP: %s" % errs)
            w["all_error_alerted"] = True
    else:
        w["all_error_streak"] = 0
        w["all_error_alerted"] = False
    if errs and len(errs) < 4:
        w["status"] = "LIVE (loi mot phan)"
    elif errs:
        w["status"] = "LOI"
    else:
        w["status"] = "LIVE"
    rx = w.get("raptorx") or {}
    fr = w.get("frantic") or {}
    w["detail"] = "Superteam seen %d listing (moi vong nay %d); RaptorX: winners=%s, %s bai nop; Taskmarket seen %d; HYRVE total %d; Frantic open %s, moved $%s. Loi nguon: %s" % (
        len(w.get("superteam_seen") or []), len(st_new_ids), rx.get("isWinnersAnnounced"),
        rx.get("submissions"), len(w.get("taskmarket_seen") or []), w.get("hyrve_total") or 0,
        fr.get("bounties_open"), fr.get("moved_usd"), errs or "khong")

# ================================================================== SELLER INBOX
def watch_seller_inbox(st, alerts):
    w = st["seller_inbox"]
    w["last_check"] = iso_vn()
    w["status"] = "CHO-CONSENT"
    w["detail"] = "Phu thuoc Gmail OAuth (chua consent) - KHONG port phan doc mail. Cho Luân consent 1 lan (giai doan 2) de doc mail Gumroad/Codester/Wirestock/Adobe/Upwork/Dreamstime."

# ================================================================== WATCHES.md
STATUS_LABEL = {"LIVE": "LIVE", "CHO-CREDENTIAL": "CHO-CREDENTIAL",
                "CHO-CONSENT": "CHO-CONSENT", "LOI": "LOI", "INIT": "INIT"}
WATCH_ROWS = [
    ("synmerco", "Synmerco"),
    ("cc0", "CC0 storefront"),
    ("moltjobs", "MoltJobs"),
    ("owockibot", "Owockibot"),
    ("fiverr", "Fiverr (qua Gmail)"),
    ("boards", "Boards (Superteam/Taskmarket/HYRVE/Frantic)"),
    ("seller_inbox", "Seller inbox (Gmail)"),
]

def write_watches_md(st, cycle_events):
    lines = []
    lines.append("# Pepper Hunter WATCHES - 7 watch kiem tien (GitHub Actions)")
    lines.append("")
    lines.append("Cap nhat: %s (VN) | Vong gan nhat: %s | Su kien vong nay: %d"
                 % (iso_vn(), st["meta"].get("last_cycle") or "-", cycle_events))
    lines.append("")
    lines.append("| Watch | Trang thai | Lan kiem gan nhat | Chi tiet |")
    lines.append("|---|---|---|---|")
    for key, name in WATCH_ROWS:
        w = st.get(key) or {}
        stat = w.get("status") or "INIT"
        if stat.startswith("LIVE"):
            stat_label = "LIVE" + stat[4:]
        else:
            stat_label = STATUS_LABEL.get(stat, stat)
        detail = (w.get("detail") or "").replace("|", "/")[:300]
        lines.append("| %s | %s | %s | %s |" % (name, stat_label, w.get("last_check") or "-", detail))
    lines.append("")
    lines.append("Ghi chu:")
    lines.append("- Watch cham tien (bid/claim) chi hanh dong khi credential tuong ung da o trong repo secrets; thieu credential thi watch chay che do cho + ghi ro o cot Chi tiet.")
    lines.append("- CC0: watch chi doc KV + bao don; fulfill brief va sweep vi agent la phase 2 (mo rong Worker CC0) - xem DOER.md.")
    lines.append("- Fiverr + Seller inbox: cho Luân consent Gmail OAuth 1 lan (giai doan 2) - chua doc mail.")
    lines.append("- Tat ca bao cao ra Telegram dung group cua he (secret TELEGRAM_CHAT_ID); khong co gi moi thi im lang, chi WATCHES.md nay cap nhat heartbeat.")
    with open(WATCHES_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

# ================================================================== git/dispatch
def git_commit_push(msg):
    if not WATCH_GIT:
        return
    def run(args):
        return subprocess.run(args, cwd=BASE_DIR, capture_output=True, text=True, timeout=120)
    try:
        run(["git", "add", "state/watches_state.json", "WATCHES.md"])
        stt = run(["git", "status", "--porcelain"])
        if not (stt.stdout or "").strip():
            return
        run(["git", "-c", "user.name=Pepper Hunter Watches", "-c", "user.email=watches@pepperresearch",
             "commit", "-m", msg])
        r = run(["git", "push", "origin", "HEAD:main"])
        if r.returncode != 0:
            # repo dung chung voi doer (commit song song) -> rebase roi push lai 1 lan
            run(["git", "pull", "--rebase", "origin", "main"])
            r = run(["git", "push", "origin", "HEAD:main"])
        if r.returncode != 0:
            log("git push loi: %s" % (r.stderr or "")[:200])
        else:
            log("Da commit+push: %s" % msg)
    except Exception as e:
        log("git loi: %s" % e)

def self_dispatch():
    if not WATCH_DISPATCH:
        return
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        log("Khong co GH_TOKEN/GITHUB_TOKEN - khong tu dispatch duoc")
        return
    env = dict(os.environ)
    env["GH_TOKEN"] = token
    try:
        r = subprocess.run(["gh", "workflow", "run", "watch.yml", "--ref", "main"],
                           cwd=BASE_DIR, capture_output=True, text=True, timeout=120, env=env)
        log("Tu dispatch run moi: rc=%d %s" % (r.returncode, (r.stdout + r.stderr)[:200]))
    except Exception as e:
        log("Dispatch loi: %s" % e)

# ================================================================== main
WATCH_FUNCS = [
    ("synmerco", watch_synmerco),
    ("cc0", watch_cc0),
    ("moltjobs", watch_moltjobs),
    ("owockibot", watch_owockibot),
    ("fiverr", watch_fiverr),
    ("boards", watch_boards),
    ("seller_inbox", watch_seller_inbox),
]

def process_cycle(st):
    alerts = []
    for name, fn in WATCH_FUNCS:
        try:
            fn(st, alerts)
        except Exception as e:
            log("Watch %s loi (da cach ly): %s" % (name, e))
            w = st[name]
            w["status"] = "LOI"
            w["detail"] = "Loi vong nay: %s" % str(e)[:200]
            w["last_check"] = iso_vn()
    sent = 0
    for a in alerts:
        if telegram_send("[Pepper Hunter Watches]\n" + a):
            sent += 1
    if alerts:
        log("Da gui %d/%d canh bao Telegram" % (sent, len(alerts)))
    return len(alerts)

def main():
    missing = []
    if not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        missing.append("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")
    if not (os.environ.get("SYNMERCO_API_KEY") or "").strip():
        missing.append("SYNMERCO_API_KEY")
    if not (os.environ.get("MOLTJOBS_API_KEY") or "").strip():
        missing.append("MOLTJOBS_API_KEY")
    if not (os.environ.get("CC0_CF_API_TOKEN") or "").strip():
        missing.append("CC0_CF_API_TOKEN")
    for m in missing:
        log("chua cau hinh: %s" % m)
    st = load_state()
    log("Watches bat dau: budget %.0f phut, poll %ds, once=%s, git=%s, dispatch=%s"
        % (LOOP_BUDGET_MIN, POLL_SEC, WATCH_ONCE, WATCH_GIT, WATCH_DISPATCH))
    start = time.monotonic()
    budget_sec = LOOP_BUDGET_MIN * 60
    last_commit = 0.0
    first = True
    while True:
        t0 = time.monotonic()
        try:
            events = process_cycle(st)
        except Exception as e:
            log("LOI TOAN VONG (da cach ly): %s" % e)
            events = 0
        st["meta"]["last_cycle"] = iso_vn()
        if first and not st["meta"].get("launch_notified"):
            rows = []
            for key, name in WATCH_ROWS:
                rows.append("- %s: %s" % (name, (st.get(key) or {}).get("status")))
            msg = ("[Pepper Hunter Watches] HE WATCH KIEM TIEN DA LEN SONG TREN GITHUB ACTIONS\n"
                   "7 watch chay vong lap 60s trong repo pepper-hunter-cron (chung nha voi Doer):\n"
                   + "\n".join(rows) +
                   "\nFiverr + Seller inbox cho consent Gmail OAuth (giai doan 2). Trang thai song: WATCHES.md trong repo.")
            if telegram_send(msg):
                st["meta"]["launch_notified"] = True
                log("Da gui tin khai truong he watch")
        first = False
        heartbeat_due = (time.monotonic() - last_commit) >= HEARTBEAT_SEC
        if events or heartbeat_due or WATCH_ONCE:
            write_watches_md(st, events)
            save_state(st)
            git_commit_push("watches: vong %s - %d su kien" % (now_vn().strftime("%H:%M"), events))
            last_commit = time.monotonic()
        else:
            save_state(st)
        if WATCH_ONCE:
            log("WATCH_ONCE=1 - thoat sau 1 vong")
            return 0
        elapsed = time.monotonic() - start
        remaining = budget_sec - elapsed
        if remaining <= 150:
            log("Sap het gio job - tu dispatch run moi roi thoat")
            self_dispatch()
            return 0
        cycle_used = time.monotonic() - t0
        time.sleep(max(5, min(POLL_SEC - cycle_used if POLL_SEC > cycle_used else 5, remaining - 120)))

if __name__ == "__main__":
    sys.exit(main())
