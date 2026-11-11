#!/usr/bin/env python3
"""Harness hanh vi cho doer.py - chay OFFLINE, mock toan bo be mat mang
(gh_api / http_json / gemini / telegram), KHONG gui comment that.

Chung minh cac cong sau su co SS14 (don bia vao issue loi game) va su co
IES-BoilerRoom (7 comment trung + bia "experienced in CUDA" tren issue
mirror gia danh escrow):
  (a) LINT NGHIEM v2: text nhan kinh nghiem CUDA/FP8 -> bi chan, thay bang
      template an toan, text bia KHONG bao gio duoc gui.
  (b) DEDUPE TRUOC GUI: issue da co comment cua Luando-tester -> 0 lan POST
      (ca duong don moi lan duong gui bo sung), entry duoc danh dau da gui.
  (c) LOC MIRROR O INTAKE: body "Conformance Mirror" -> skipped_trap ngay
      tu dang ky + migration state cu + cong kiem chung chan.
  (d) SS14 + cac ca cu: khong tin hieu tien that -> skipped_nopay, 0 gui;
      aggregator bi bo; repo bay theo ten -> skipped_trap; keo sach gui
      dung 1 comment nguyen van; keo chua ghi ngan sach co doan hoi tien;
      placeholder [X] duoc sanitize; repo < 30 ngay toan bai escrow ->
      bay; self_dispatch khong dispatch khi da co run khac dang active.

Cach chay: python3 tests/harness_doer.py  (thoat 0 neu tat ca PASS)
"""
import importlib.util, json, os, re, shutil, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="doer-harness-")
shutil.copy(os.path.join(ROOT, "doer.py"), os.path.join(TMP, "doer.py"))
os.environ["GITHUB_PAT"] = "classic-test-pat"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_CHAT_ID", None)

spec = importlib.util.spec_from_file_location("doer_harness_mod", os.path.join(TMP, "doer.py"))
doer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doer)

# ---------------------------------------------------------------- Mock layer
POSTS = []          # (path, obj) - moi POST comment/PR deu ghi lai
TG = []
ISSUES = {}         # (owner, repo, num) -> raw issue dict
COMMENTS = {}       # (owner, repo, num) -> [raw comment dict]
REPOS = {}          # (owner, repo) -> raw repo dict
REPO_ISSUES = {}    # (owner, repo) -> [raw issue dict]
GEMINI_TEXT = [""]


def _parse_issue_path(path):
    m = re.match(r"/repos/([^/]+)/([^/]+)/issues/(\d+)", path or "")
    return (m.group(1), m.group(2), int(m.group(3))) if m else None


def fake_gh_api(method, path, obj=None):
    if method == "POST" and re.search(r"/issues/\d+/comments$", path or ""):
        POSTS.append((path, obj))
        return 201, {"html_url": "https://github.com/x/y/issues/1#issuecomment-1"}
    if method == "POST":
        POSTS.append((path, obj))
        return 201, {"html_url": "https://github.com/x/y/pull/9", "number": 9}
    if method == "GET":
        if path.startswith("/search/issues"):
            return 200, {"items": []}
        if path == "/user":
            return 200, {"login": "Luando-tester"}
        key = _parse_issue_path(path)
        if key and "/comments" in path:
            return 200, COMMENTS.get(key, [])
        if key:
            d = ISSUES.get(key)
            return (200, d) if d else (404, {})
        m = re.match(r"/repos/([^/]+)/([^/]+)/issues\?", path or "")
        if m:
            return 200, REPO_ISSUES.get((m.group(1), m.group(2)), [])
        m = re.match(r"/repos/([^/]+)/([^/]+)$", path or "")
        if m:
            d = REPOS.get((m.group(1), m.group(2)))
            return (200, d) if d else (404, {})
    return 404, {}


doer.gh_api = fake_gh_api
doer.http_json = lambda *a, **k: (404, {})
doer.telegram_send = lambda text: (TG.append(text), True)[1]
doer.gemini_generate_pool = lambda pool, ps, prompt: (GEMINI_TEXT[0], "gemini-mock")
POOL = ["key1"]
POOL_STATE = {"dead": set(), "gone": {}}

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %s%s" % ("PASS" if cond else "FAIL", name, (" | " + str(detail)[:180]) if (detail and not cond) else ""))


def raw_issue(title, body, labels=None, state="open", assignees=None, comments=0):
    return {"state": state, "title": title, "body": body,
            "labels": [{"name": l} for l in (labels or [])],
            "assignees": [{"login": a} for a in (assignees or [])],
            "comments": comments}


def entry_for(owner, repo, num, title, budget=100.0, pack="", status="new"):
    return {"title": title, "url": "https://github.com/%s/%s/issues/%d" % (owner, repo, num),
            "slug": "%s-%s-%d" % (owner, repo, num), "budget_usd": budget,
            "pack": pack, "status": status, "files": [],
            "type": "code", "mode": "cho_duoc_chon"}


# ================================================================ (d1) SS14
SS14_KEY = ("space-wizards", "space-station-14", 44876)
ISSUES[SS14_KEY] = raw_issue(
    "[Bug] Bounty system does not pay out in cargo",
    "The in-game bounty system in the cargo department fails to pay bounties "
    "to the station account after delivery. Steps to reproduce in game...",
    labels=["T: Bugfix", "A: Cargo"])
e = entry_for(*SS14_KEY, "[Bug] Bounty system does not pay out in cargo", budget=None)
e["mode"] = "cho_duoc_chon"
doer.make_apply(e, POOL, POOL_STATE, doer.fetch_issue_info(e["url"]))
check("SS14: presend chan -> skipped_nopay", e["status"] == "skipped_nopay", e.get("status"))
check("SS14: 0 comment duoc gui", len(POSTS) == 0, POSTS)

# ================================================================ (a) CUDA bia
IES_KEY = ("IES-BoilerRoom", "cuda-warp-allreduce-verifier", 1)
IES_BODY = ("> **Automated CI Conformance Mirror Notice**: Automated IEEE-754 regression runner issue; "
            "manual pull requests from human engineers are not reviewed on this mirror.\n"
            "- Escrow Rail: algora.io / polar.sh / opire.dev\n"
            "- Funding Status: Held in escrow - Reward: $450 USDC\n"
            "- **Specification Shards**: shards/spec_01.json .. shards/spec_64.json")
ISSUES[IES_KEY] = raw_issue("[Escrowed $450 USDC] Align SM90 warp butterfly accumulator rounding",
                            IES_BODY, labels=["bounty"])
CUDA_TEXT = ("Hi! I'm PepperResearch and I am experienced in CUDA kernel optimization and "
             "FP8 numerical precision alignment. I have deep expertise in SM90 warp "
             "butterfly reduction and 8+ years of GPU programming. My plan: fix the "
             "rounding, run the verifier suite, open a PR. ETA 2 days. Please assign me.")
deal_cuda = {"title": ISSUES[IES_KEY]["title"], "url": "https://github.com/%s/%s/issues/%d" % IES_KEY,
             "budget_usd": 450.0}
bia = doer.lint_application(CUDA_TEXT, deal_cuda)
check("(a) LINT bat duoc cau 'experienced in CUDA...'", len(bia) >= 1, bia)
safe, bia2 = doer.gate_outbound_text(CUDA_TEXT, deal_cuda, kind="apply")
check("(a) gate thay TOAN BO bang template an toan",
      "CUDA" not in safe and "FP8" not in safe and "butterfly" not in safe.lower()
      and "PepperResearch" in safe, safe[:120])
# E2E: keo co tin hieu tien gia (escrow $450) nhung body mirror -> make_apply bi chan o presend
POSTS.clear()
e = entry_for(*IES_KEY, ISSUES[IES_KEY]["title"], budget=450.0, pack=IES_BODY)
GEMINI_TEXT[0] = CUDA_TEXT
doer.make_apply(e, POOL, POOL_STATE, doer.fetch_issue_info(e["url"]))
check("(c) IES mirror: make_apply bi chan -> skipped_trap", e["status"] == "skipped_trap", e.get("status"))
check("(c) IES mirror: 0 comment duoc gui", len(POSTS) == 0, POSTS)

# Mirror nhung gia su chi co o intake (pack), info sach -> register_deal phai skipped_trap
MIR_KEY = ("somedev", "x402-conf-suite", 7)
ISSUES[MIR_KEY] = raw_issue("Improve the conformance suite docs",
                            "Docs need work. Bounty $120 USDC for the fix.", labels=["bounty"])
st8 = {}
ent = doer.register_deal(st8, {"title": "Improve the conformance suite docs",
                               "url": "https://github.com/%s/%s/issues/%d" % MIR_KEY,
                               "budget_usd": 120.0, "pack": IES_BODY})
check("(c) intake: pack mirror -> dang ky skipped_trap",
      ent is not None and ent.get("status") == "skipped_trap", ent and ent.get("status"))

# Migration: entry applied cu co pack mirror -> process_cycle chuyen skipped_trap
MIG_KEY = ("otherdev", "wasm-mirror-thing", 3)
ISSUES[MIG_KEY] = raw_issue("Fix suite", "Bounty $50 USDC.", labels=["bounty"])
st9 = {"https://github.com/%s/%s/issues/%d" % MIG_KEY:
       entry_for(*MIG_KEY, "Fix suite", budget=50.0, pack=IES_BODY, status="applied")}
st9["https://github.com/%s/%s/issues/%d" % MIG_KEY]["apply_sent"] = True
POSTS.clear()
doer.process_cycle(st9, POOL, POOL_STATE)
check("(c) migration: applied + pack mirror -> skipped_trap",
      st9["https://github.com/%s/%s/issues/%d" % MIG_KEY]["status"] == "skipped_trap")
check("(c) migration: 0 comment duoc gui", len(POSTS) == 0, POSTS)

# Repo < 30 ngay, toan bai escrow/conformance -> bay theo tuoi repo
REPOS[("IES-BoilerRoom", "cuda-warp-allreduce-verifier")] = {"created_at": "2026-11-09T21:11:47Z"}
REPO_ISSUES[("IES-BoilerRoom", "cuda-warp-allreduce-verifier")] = [
    {"title": "[Escrowed $450 USDC] Align SM90 warp butterfly accumulator rounding"}]
doer._REPO_AGE_CACHE.clear()
rsn = doer.repo_age_trap_reason("https://github.com/IES-BoilerRoom/cuda-warp-allreduce-verifier/issues/1")
check("(c) repo 2 ngay tuoi + toan bai escrow -> bay", bool(rsn), rsn)
REPOS[("olddev", "mature-lib")] = {"created_at": "2021-03-01T00:00:00Z"}
check("(c) repo gia -> khong bi bat", doer.repo_age_trap_reason(
    "https://github.com/olddev/mature-lib/issues/5") is None)

# ============================================================ (b) DEDUPE
DUP_KEY = ("acme", "report-tool", 12)
ISSUES[DUP_KEY] = raw_issue("Automate weekly report generation script ($150)",
                            "Write a Python script. Reward $150 USD via Opire.", labels=["bounty"])
COMMENTS[DUP_KEY] = [{"user": {"login": "Luando-tester"}, "author_association": "NONE",
                      "id": 555, "html_url": "https://github.com/acme/report-tool/issues/12#issuecomment-555",
                      "body": "Hi! I'm PepperResearch - I'd like to take on this issue."}]
POSTS.clear()
GEMINI_TEXT[0] = "Hi! I'm PepperResearch. My plan: build the script, test it, open a PR. ETA 3 days."
e = entry_for(*DUP_KEY, ISSUES[DUP_KEY]["title"], budget=150.0)
doer.make_apply(e, POOL, POOL_STATE, doer.fetch_issue_info(e["url"]))
check("(b) make_apply: da co comment cua minh -> 0 POST", len(POSTS) == 0, POSTS)
check("(b) make_apply: entry duoc danh dau apply_sent + dedupe_skip",
      e.get("apply_sent") is True and bool(e.get("apply_dedupe_skip")), e.get("apply_sent"))

# resend_apply voi APPLY.md chua don BIA + issue da co comment -> dedupe thang, 0 POST
slug_dir = os.path.join(TMP, "deliverables", e["slug"])
os.makedirs(slug_dir, exist_ok=True)
with open(os.path.join(slug_dir, "APPLY.md"), "w", encoding="utf-8") as f:
    f.write("# Don\n\n## Noi dung comment se gui\n\n" + CUDA_TEXT + "\n")
e2 = entry_for(*DUP_KEY, ISSUES[DUP_KEY]["title"], budget=150.0, status="applied")
e2["files"] = ["deliverables/%s/APPLY.md" % e["slug"]]
e2["apply_sent"] = False
POSTS.clear()
ok = doer.resend_apply(e2)
check("(b) resend_apply: dedupe -> True, 0 POST, apply_sent=True",
      ok is True and len(POSTS) == 0 and e2.get("apply_sent") is True, (ok, POSTS))

# resend_apply KHONG trung: don bia -> gate thay template roi moi gui (0 text bia)
COMMENTS[DUP_KEY] = []
POSTS.clear()
e3 = entry_for(*DUP_KEY, ISSUES[DUP_KEY]["title"], budget=150.0, status="applied")
e3["files"] = ["deliverables/%s/APPLY.md" % e["slug"]]
e3["apply_sent"] = False
ok = doer.resend_apply(e3)
sent_body = (POSTS[0][1] or {}).get("body", "") if POSTS else ""
check("(a) resend_apply: don bia bi thay bang template truoc khi gui",
      ok is True and len(POSTS) == 1 and "CUDA" not in sent_body and "experienced" not in sent_body,
      sent_body[:120])

# ============================================================ (d) cac ca cu
# Keo sach + don sach -> gui dung 1 comment, nguyen van
OK_KEY = ("acme", "report-tool", 13)
ISSUES[OK_KEY] = raw_issue("Automate weekly report generation script ($150)",
                           "Write a Python script. Reward $150 USD via Opire.", labels=["bounty"])
COMMENTS[OK_KEY] = []
CLEAN_TEXT = ("Hi! I'm PepperResearch. My experience is in Python automation and Telegram "
              "bots, plus cited research writing published on dev.to. My plan: 1) read the "
              "spec, 2) build the script, 3) test it, 4) open a PR. ETA 3 days. "
              "Please assign me or confirm I can proceed.")
GEMINI_TEXT[0] = CLEAN_TEXT
POSTS.clear()
e = entry_for(*OK_KEY, ISSUES[OK_KEY]["title"], budget=150.0)
doer.make_apply(e, POOL, POOL_STATE, doer.fetch_issue_info(e["url"]))
sent_body = (POSTS[0][1] or {}).get("body", "") if POSTS else ""
check("(d) keo sach: gui dung 1 comment", len(POSTS) == 1 and e.get("apply_sent") is True, POSTS)
check("(d) keo sach: don sach qua LINT nguyen van", sent_body == CLEAN_TEXT, sent_body[:120])
check("(d) LINT: cau nhan kinh nghiem dung ho so that -> sach",
      doer.lint_application(CLEAN_TEXT, {"title": ISSUES[OK_KEY]["title"],
                                         "url": e["url"], "budget_usd": 150.0}) == [])
check("(d) LINT: template an toan tu no phai sach",
      doer.lint_application(doer.template_apply({"title": "X", "url": e["url"], "budget_usd": 5}),
                            {"title": "X", "url": e["url"], "budget_usd": 5}) == [])

# Keo chua ghi ngan sach -> don co doan hoi tien bat buoc
NB_KEY = ("acme", "report-tool", 14)
ISSUES[NB_KEY] = raw_issue("Write the onboarding guide (bounty)",
                           "Docs task. Bounty via Algora, amount in the bounty board.", labels=["bounty"])
GEMINI_TEXT[0] = CLEAN_TEXT
POSTS.clear()
e = entry_for(*NB_KEY, ISSUES[NB_KEY]["title"], budget=None)
doer.make_apply(e, POOL, POOL_STATE, doer.fetch_issue_info(e["url"]))
sent_body = (POSTS[0][1] or {}).get("body", "") if POSTS else ""
check("(d) keo chua ghi ngan sach: don co doan hoi tien",
      "exact bounty amount" in sent_body, sent_body[-100:])

# Sanitize placeholder [X]
check("(d) sanitize [X] days -> 3 days",
      doer.sanitize_comment_body("ETA: [X] days") == "ETA: 3 days")

# Aggregator -> khong dang ky
st10 = {}
ent = doer.register_deal(st10, {"title": "Bounty Alert: new paid opportunities today",
                                "url": "https://github.com/agg/spam/issues/1",
                                "budget_usd": None, "pack": "list of things"})
check("(d) aggregator: khong dang ky vao state", ent is None and len(st10) == 0)

# Repo bay theo ten -> skipped_trap (ghi nhan, khong gui)
TRAP_KEY = ("PhanKhoa95", "oss-bot-trap-benchmark", 88)
ISSUES[TRAP_KEY] = raw_issue("[Bounty $1,600] security hardening task",
                             "Reward $1,600 USDC.", labels=["bounty"])
st11 = {}
ent = doer.register_deal(st11, {"title": ISSUES[TRAP_KEY]["title"],
                                "url": "https://github.com/%s/%s/issues/%d" % TRAP_KEY,
                                "budget_usd": 1600.0, "pack": "Reward $1,600 USDC."})
check("(d) repo bay theo ten -> skipped_trap", ent is not None and ent.get("status") == "skipped_trap",
      ent and ent.get("status"))

# Gate cho than PR: body co cau bia -> safe_pr_body
pr_safe, pr_bia = doer.gate_outbound_text(
    "This PR is by a developer experienced in CUDA kernel optimization.",
    {"title": "T", "url": "https://github.com/a/b/issues/1", "budget_usd": 1}, kind="pr")
check("(a) gate PR body: bia -> safe_pr_body", bool(pr_bia) and "CUDA" not in pr_safe, pr_safe[:80])

# ============================================================ single-flight
CALLS = []


class FakeCompleted:
    def __init__(self, out):
        self.returncode = 0
        self.stdout = out
        self.stderr = ""


def fake_run(args, **kw):
    CALLS.append(args)
    if "api" in args:
        return FakeCompleted(FAKE_RUNS_OUT[0])
    return FakeCompleted("")


FAKE_RUNS_OUT = ["42999999999\tin_progress\n111\tsuccess\n"]
os.environ["GITHUB_RUN_ID"] = "222"
os.environ["GH_TOKEN"] = "fake-actions-token"
doer.DOER_DISPATCH = True  # ngoai Actions mac dinh tat - bat len de test nhanh nay
_orig_run = doer.subprocess.run
doer.subprocess.run = fake_run
try:
    CALLS.clear()
    doer.self_dispatch()
    dispatched = any("workflow" in a and "run" in a for a in CALLS)
    check("(sf) co run khac dang in_progress -> KHONG dispatch", not dispatched, CALLS)
    FAKE_RUNS_OUT[0] = "222\tin_progress\n"
    CALLS.clear()
    doer.self_dispatch()
    dispatched = any("workflow" in a and "run" in a for a in CALLS)
    check("(sf) chi con run cua minh -> dispatch binh thuong", dispatched, CALLS)
finally:
    doer.subprocess.run = _orig_run

# ================================================================ tong ket
fails = [r for r in RESULTS if not r[1]]
print("\nTong: %d/%d PASS" % (len(RESULTS) - len(fails), len(RESULTS)))
if fails:
    print("CAC CA FAIL:")
    for name, _, detail in fails:
        print(" -", name, "|", detail)
    sys.exit(1)
print("HARNESS XANH TOAN BO")
