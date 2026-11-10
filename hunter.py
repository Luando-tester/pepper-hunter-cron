#!/usr/bin/env python3
# Pepper Hunter - ban tham chieu chay local / GitHub Actions (workflow_dispatch).
# Runner dinh ky chinh la Cloudflare Worker (worker/worker.js); file nay giu de
# test local va chay tay viec nang (sinh work pack day du, ghi file vao repo).
# Chi dung Python stdlib. Khong chua bat ky key/token nao - doc tu env:
#   GEMINI_API_KEYS - POOL toi da 10 key, ngan cach bang dau phay hoac xuong dong,
#     xoay vong giong tool local (het quota key nay -> key ke).
#   GEMINI_API_KEY - (cu, van ho tro) neu chi co bien nay thi pool = 1 key nay.
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "state" / "seen.json"
PACKS_DIR = BASE / "packs"

GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
# LUOI NOI RONG (11/11): bo truy van dong bo ca 3 tang (hunter.py + doer.py +
# worker.js). Moi truy van la (query, hi): hi=True = tin hieu cao (label bounty
# / co tien trong tieu de) -> cap 3 issue/repo; hi=False -> cap 2 issue/repo.
# File nay chay tron bo moi luot; Worker xoay vong theo tap vi goi khong auth.
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
MAX_NEW_PER_RUN = 12
PER_PAGE = 30

BANNED = [
    "shill", "spam", "fake engagement", "fake follower", "fake review",
    "money mule", "mule account", "laundering", "gambling", "betting",
    "casino", "captcha farm", "captcha solving", "airdrop farm",
    "pump and dump", "paid retweet farm",
    "generate gmv", "qualifying gmv", "fake volume", "wash trading", "wash trade",
    "simulated volume", "bot traffic", "fake traffic",
]

ASK_MONEY_EN = ("Hi! I'm interested in this bounty and I'd like to start soon. Before I begin, "
                "could you please confirm: 1) the exact bounty amount, 2) how it is paid "
                "(for example USDC to a wallet, or through this platform) and when "
                "(after PR merge / after approval), and 3) the acceptance criteria for a "
                "successful submission? Thank you!")
CLAIM_EN = ("Hi! I'd like to claim this issue and work on it.\n"
            "My plan: 1) study the task and the codebase, 2) implement it in my fork on a "
            "separate branch, 3) test it locally against the repo's checks, 4) open a pull "
            "request that references this issue.\nETA: [X] days. If the task is still open, "
            "please assign it to me or confirm that I can proceed. Thank you!")


def log(msg):
    print("[PH %s] %s" % (datetime.now().strftime("%H:%M:%S"), msg), flush=True)


MAX_GEMINI_KEYS = 10


def parse_key_pool():
    """Pool key Gemini tu env: GEMINI_API_KEYS (ngan cach dau phay/xuong dong,
    toi da 10, trung thi bo). Thieu thi lui ve GEMINI_API_KEY cu = pool 1 key."""
    raw = (os.environ.get("GEMINI_API_KEYS") or "").strip()
    parts = []
    if raw:
        parts = [p.strip() for p in re.split(r"[,\n]", raw) if p.strip()]
    else:
        single = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if single:
            parts = [single]
    pool, seen_keys = [], set()
    for k in parts:
        if k in seen_keys:
            continue
        seen_keys.add(k)
        pool.append(k)
        if len(pool) >= MAX_GEMINI_KEYS:
            break
    return pool


def http_json(url, data=None, headers=None, timeout=25):
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    req.add_header("User-Agent", "pepper-hunter/1.0")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_budget(title):
    """Trich ngan sach tu title. Tra (so USD hoac None, ghi chu). Cam bia so."""
    if "credit" in title.lower():
        return None, "site credit (khong phai tien mat/USDC)"
    m = re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)", title)
    if m:
        return float(m.group(1).replace(",", "")), "ghi tren bai dang"
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s?(USDC|USDT|USD)\b", title, re.I)
    if m:
        return float(m.group(1).replace(",", "")), "ghi tren bai dang"
    return None, ""


def clean_gate(text):
    low = (text or "").lower()
    hits = [w for w in BANNED if w in low]
    return hits


def is_site_credit(text):
    """'site credit' = tra bang tin dung noi bo cua san, KHONG phai tien that ->
    bo qua ngay tai cong loc: khong tinh new_clean, khong goi Gemini, khong
    gui Telegram (dong bo luat tool local: site credit khong phai tien)."""
    return "site credit" in (text or "").lower()


# Cong chan REPO BAY BOT (dong bo doer.py + worker.js): owner/ten repo chua
# "trap"/"honeypot"/"benchmark" = bay du bot san bounty -> bo qua han.
TRAP_MARKERS = ["trap", "honeypot", "benchmark"]


def is_trap_repo(repo):
    low = (repo or "").lower()
    return any(m in low for m in TRAP_MARKERS)


def fetch_bounties():
    """Keo keo THAT tu GitHub Search API. Tra (items, errors)."""
    items, errors, seen_url = [], [], set()
    per_repo = {}
    for q, hi in SEARCH_QUERIES:
        cap = MAX_PER_REPO_HI if hi else MAX_PER_REPO
        url = ("https://api.github.com/search/issues?q=" + urllib.parse.quote(q)
               + "&sort=created&order=desc&per_page=%d" % PER_PAGE)
        try:
            data = http_json(url)
        except Exception as e:
            errors.append("GitHub search '%s' loi: %s" % (q, e))
            log("LOI nguon GitHub (%s): %s" % (q, e))
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
            repo = ""
            ru = it.get("repository_url", "")
            if "/repos/" in ru:
                repo = ru.split("/repos/", 1)[1]
            if per_repo.get(repo, 0) >= cap:
                continue
            if is_trap_repo(repo):
                log("BO QUA repo bay bot (%s): %s" % (repo, title[:70]))
                continue
            per_repo[repo] = per_repo.get(repo, 0) + 1
            seen_url.add(html)
            budget, budget_note = extract_budget(title)
            items.append({
                "title": title, "url": html, "repo": repo,
                "number": it.get("number"),
                "created_at": (it.get("created_at") or "")[:10],
                "excerpt": re.sub(r"\s+", " ", (it.get("body") or ""))[:600],
                "budget_usd": budget, "budget_note": budget_note,
                "labels": [l.get("name", "") for l in it.get("labels", []) if isinstance(l, dict)],
            })
        log("GitHub query '%s': tong cong tich luy %d ung vien" % (q, len(items)))
    return items, errors


def gemini_call(key, model, prompt):
    """1 lan goi Gemini (1 key x 1 model). Tra (text, http_status_hoac_None, detail).
    Key 'AQ...' di query auth ?key=, key 'AIza...' di header x-goog-api-key."""
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
    headers = {"Content-Type": "application/json"}
    if str(key).startswith("AQ"):
        url += "?key=" + urllib.parse.quote(key)
    else:
        headers["x-goog-api-key"] = key
    try:
        data = http_json(url, data=body, headers=headers, timeout=40)
        return data["candidates"][0]["content"]["parts"][0]["text"], 200, ""
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")[:160]
        except Exception:
            pass
        return "", e.code, detail
    except Exception as e:
        return "", None, "%s: %s" % (type(e).__name__, e)


def gemini_generate_pool(keys, prompt, pool_state):
    """Xoay POOL key giong tool local. pool_state giu trong 1 vong chay:
    {'dead': set(idx), 'gone': {idx: set(model)}}.
    - 429 (het quota): chuyen model ke cua CUNG key; het model -> sang key ke.
    - 404 model: bo qua model do cho key do trong ca vong chay.
    - 400/401/403 (key chet): bo han key do trong ca vong chay.
    Thanh cong: log key index + model (chi so thu tu, khong in key).
    Tra (text, key_index_1based_hoac_0, model, last_error). Loi 1 key khong giet vong chay."""
    last_err = ""
    for idx, key in enumerate(keys):
        if idx in pool_state["dead"]:
            continue
        gone = pool_state["gone"].setdefault(idx, set())
        for model in GEMINI_MODELS:
            if model in gone:
                continue
            text, status, detail = gemini_call(key, model, prompt)
            if text:
                log("Gemini OK: key #%d model %s" % (idx + 1, model))
                return text, idx + 1, model, ""
            last_err = "key #%d %s HTTP %s %s" % (idx + 1, model, status, detail)
            log("Gemini %s" % last_err)
            if status in (400, 401, 403):
                pool_state["dead"].add(idx)
                log("Gemini key #%d chet (HTTP %s) -> bo key nay trong vong chay, sang key ke" % (idx + 1, status))
                break
            if status == 404:
                gone.add(model)
                log("Gemini key #%d model %s 404 -> bo qua model nay cho key nay" % (idx + 1, model))
                continue
            if status == 429:
                log("Gemini key #%d het quota o %s (429) -> chuyen model ke cua cung key" % (idx + 1, model))
                continue
            # Loi khac (5xx / mang): thu model ke, khong giet vong chay.
        else:
            log("Gemini key #%d het model kha dung -> sang key ke" % (idx + 1))
    return "", 0, "", last_err


def template_pack(item):
    lines = [
        "# Work pack (template offline - chua co/chua dung duoc Gemini)",
        "",
        "- Keo: %s" % item["title"],
        "- San: GitHub - %s" % item["repo"],
        "- Link: %s" % item["url"],
        "- Dang: %s" % (item["created_at"] or "khong ro"),
        "- Ngan sach: %s" % (("$%s" % item["budget_usd"]) if item["budget_usd"] else "CHUA GHI tren bai dang"),
    ]
    if item.get("budget_note"):
        lines.append("- Ghi chu ngan sach: %s" % item["budget_note"])
    lines += ["", "## Yeu cau (trich bai dang)", item.get("excerpt") or "(bai dang khong co mo ta)", ""]
    if not item["budget_usd"]:
        lines += ["## BAT BUOC: hoi ro tien truoc khi lam",
                  "Keo chua ghi ngan sach - khong lam mu. Gui comment nay truoc:",
                  "", "```", ASK_MONEY_EN, "```", ""]
    lines += ["## Ke hoach lam",
              "1. Doc ky issue + repo (README, huong dan dong gop).",
              "2. Comment nhan viec (mau duoi), cho assign/xac nhan neu repo yeu cau.",
              "3. Fork, tao branch rieng, lam + tu test theo check cua repo.",
              "4. Mo PR ghi 'Closes #%s', mo ta ro thay doi + cach test." % item.get("number"),
              "5. Theo doi review, sua theo gop y, cho merge + xac nhan tra thuong.",
              "", "## Mau comment nhan viec", "", "```", CLAIM_EN, "```", ""]
    return "\n".join(lines)


def gemini_pack(keys, pool_state, item):
    prompt = ("Ban la tro ly chuan bi 'work pack' cho freelancer Viet Nam lam 1 keo GitHub bounty SACH.\n"
              "Keo: %s\nRepo: %s\nLink: %s\nNgan sach trich tu title: %s\nMo ta: %s\n"
              "Viet bang tieng Viet, ngan gon, dung cau truc: 1) Tom tat yeu cau that su phai lam; "
              "2) Ke hoach lam tung buoc (kem cach tu kiem tra); 3) Khung deliverable (neu la code: cau truc file/doan khung; "
              "neu la bai viet: dan y); 4) Rui ro/diem chua ro can hoi lai nguoi dang. %s"
              % (item["title"], item["repo"], item["url"],
                 ("$%s" % item["budget_usd"]) if item["budget_usd"] else "CHUA GHI",
                 item.get("excerpt") or "(khong co mo ta)",
                 "Vi ngan sach CHUA GHI: chen them mau comment tieng Anh hoi ro so tien, cach tra (USDC/platform) va tieu chi nghiem thu - bat buoc hoi truoc khi lam." if not item["budget_usd"] else ""))
    text, key_idx, model, err = gemini_generate_pool(keys, prompt, pool_state)
    if not text:
        log("Gemini: tat ca key deu fail cho '%s' (loi cuoi: %s) -> dung template offline" % (item["title"][:50], err))
        return template_pack(item), "template (tat ca key Gemini deu fail: %s)" % err
    head = "# Work pack (Gemini soan)\n\n- Keo: %s\n- Link: %s\n- Ngan sach: %s\n\n---\n\n" % (
        item["title"], item["url"], ("$%s" % item["budget_usd"]) if item["budget_usd"] else "CHUA GHI")
    return head + text, "gemini (key #%d, %s)" % (key_idx, model)


def telegram_send(token, chat_id, text):
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3900],
                                   "disable_web_page_preview": "false"}).encode("utf-8")
    try:
        resp = http_json(url, data=data, timeout=20)
        return bool(resp.get("ok")), ""
    except Exception as e:
        return False, str(e)


def main():
    gemini_keys = parse_key_pool()
    pool_state = {"dead": set(), "gone": {}}
    tg_token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    tg_chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

    missing = []
    if not gemini_keys:
        missing.append("GEMINI_API_KEYS")
        log("chua cau hinh: GEMINI_API_KEYS (hoac GEMINI_API_KEY) - se dung work pack template offline")
    else:
        log("Gemini pool: %d key (xoay vong, toi da %d)" % (len(gemini_keys), MAX_GEMINI_KEYS))
    if not tg_token:
        missing.append("TELEGRAM_BOT_TOKEN")
        log("chua cau hinh: TELEGRAM_BOT_TOKEN - se khong gui thong bao Telegram")
    if not tg_chat:
        missing.append("TELEGRAM_CHAT_ID")
        log("chua cau hinh: TELEGRAM_CHAT_ID - se khong gui thong bao Telegram")
    if len(missing) == 3:
        log("chua cau hinh: ca 3 bien deu thieu -> thoat em, khong lam gi ca. "
            "Dat secrets roi chay lai (xem README).")
        return 0

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    seen = {}
    if STATE_FILE.exists():
        try:
            seen = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log("seen.json hong (%s) -> bat dau lai tu state rong" % e)
            seen = {}

    items, errors = fetch_bounties()
    log("Tim thay %d ung vien tho tu GitHub (loi nguon: %d)" % (len(items), len(errors)))

    new_clean = []
    dirty = 0
    skipped_site_credit = 0
    processed = 0
    for it in items:
        if it["url"] in seen:
            continue
        if processed >= MAX_NEW_PER_RUN:
            break
        hits = clean_gate(it["title"] + " " + it.get("excerpt", ""))
        seen[it["url"]] = datetime.now().strftime("%Y-%m-%d %H:%M")
        processed += 1
        if hits:
            dirty += 1
            log("LOAI BAN (dinh tu khoa: %s): %s" % (", ".join(hits), it["title"][:70]))
            continue
        if is_site_credit(it["title"] + " " + it.get("excerpt", "")):
            skipped_site_credit += 1
            log("bo qua: site credit, khong phai tien that: %s" % it["title"][:70])
            continue
        slug = "gh-%s-%s" % (it["repo"].replace("/", "-"), it.get("number") or "x")
        if gemini_keys:
            pack_text, mode = gemini_pack(gemini_keys, pool_state, it)
        else:
            pack_text, mode = template_pack(it), "template (chua co Gemini key)"
        pack_path = PACKS_DIR / (slug + ".md")
        pack_path.write_text(pack_text, encoding="utf-8")
        it["pack"] = "packs/%s.md" % slug
        it["pack_mode"] = mode
        new_clean.append(it)
        log("KEO THAT MOI (SACH): %s | %s | pack: %s (%s)"
            % (it["title"][:70], ("$%s" % it["budget_usd"]) if it["budget_usd"] else "chua ghi ngan sach",
               it["pack"], mode))

    STATE_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")
    log("Da xu ly %d keo moi (sach: %d, ban bi loai: %d, bo qua site credit: %d). Tong seen: %d"
        % (processed, len(new_clean), dirty, skipped_site_credit, len(seen)))

    if new_clean and tg_token and tg_chat:
        for it in new_clean:
            msg = ("[Pepper Hunter] KEO THAT MOI - SACH\n%s\nSan: GitHub %s\nNgan sach: %s\nLink: %s\nWork pack: %s (%s)"
                   % (it["title"], it["repo"],
                      ("$%s" % it["budget_usd"]) if it["budget_usd"] else "chua ghi tren bai dang",
                      it["url"], it["pack"], it["pack_mode"]))
            ok, err = telegram_send(tg_token, tg_chat, msg)
            log("Telegram %s: %s%s" % (it["title"][:40], "OK" if ok else "LOI", (" - " + err) if err else ""))
    elif new_clean:
        log("Co %d keo sach moi nhung thieu Telegram token/chat_id -> chi ghi pack, khong gui." % len(new_clean))
    else:
        log("Khong co keo sach moi vong nay.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
