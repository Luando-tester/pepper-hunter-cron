// Pepper Hunter - Cloudflare Worker: RUNNER CHINH chay dinh ky bang cron trigger.
// Logic port tu hunter.py: keo keo THAT tu GitHub Search (bo truy van noi rong
// 13 truy van / 4 tap xoay vong theo tick - xem QUERY_SETS) -> cong sach
// -> chong trung bang KV (binding SEEN) -> Gemini soan work pack -> bao Telegram.
// Secrets (dat bang wrangler secret put / dashboard, KHONG ghi vao repo):
//   GEMINI_API_KEYS - POOL toi da 10 key Gemini, ngan cach bang dau phay hoac
//     xuong dong; xoay vong giong tool local (het quota key nay -> key ke).
//   GEMINI_API_KEY - (cu, van ho tro) neu chi co bien nay thi pool = 1 key nay.
//   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
// Routes: GET / -> trang thai; GET /run -> chay 1 vong ngay va tra JSON bao cao;
//   GET /latest -> JSON vong chay gan nhat (KV "run:last"): keo SACH moi + pack,
//   kem "queue": HANG DOI TICH LUY (KV "queue", cap 100, dedupe theo url) chua
//   moi keo sach tung thay - cho tang TU LAM (doer) doc va tu lam san pham
//   (run:last chi giu 1 vong nen queue la noi bat lai keo da troi).

const GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"];
// LUOI NOI RONG (11/11): bo truy van dong bo ca 3 tang (worker.js + hunter.py +
// doer.py). Moi truy van co co hi = tin hieu cao (label bounty / co tien trong
// tieu de). Worker goi GitHub Search KHONG auth (~10 req/phut theo IP egress
// dung chung) nen XOAY VONG theo tick: moi tick chi chay 1 tap con (3-4 truy
// van), chi so tap = phut UTC hien tai mod so tap - khong can luu trang thai.
// Doer (auth, 30 req/phut) chay TRON bo moi vong; hunter.py chay tron bo moi
// luot chay tay. Moi ung vien van qua NGUYEN cong sach hien co.
const QUERY_SETS = [
  // Tap 0 - cot loi: label:bounty x 3 y dinh (bo truy van goc)
  [
    { q: "is:issue is:open label:bounty code", hi: true },
    { q: 'is:issue is:open label:bounty "AI agent"', hi: true },
    { q: "is:issue is:open label:bounty writing", hi: true },
  ],
  // Tap 1 - tieu de/tien: "bounty" trong tieu de KHONG can label + dau hieu tien
  [
    { q: "is:issue is:open bounty in:title", hi: true },
    { q: 'is:issue is:open "bounty $" in:title', hi: true },
    { q: "is:issue is:open USDC bounty", hi: true },
  ],
  // Tap 2 - label bounty tran (keo khong chua tu y dinh) + reward + help wanted
  [
    { q: "is:issue is:open label:bounty", hi: true },
    { q: "is:issue is:open reward bounty in:title", hi: false },
    { q: 'is:issue is:open label:"help wanted" bounty', hi: false },
  ],
  // Tap 3 - nen tang bounty (algora/opire) + help wanted/reward + paid task
  [
    { q: "is:issue is:open algora bounty", hi: false },
    { q: "is:issue is:open opire bounty", hi: false },
    { q: 'is:issue is:open label:"help wanted" reward', hi: false },
    { q: 'is:issue is:open "paid task" bounty', hi: false },
  ],
];
const MAX_PER_REPO = 2;
const MAX_NEW_PER_RUN = 12;
const PER_PAGE = 30;
const MAX_GEMINI_KEYS = 10;

// Pool key Gemini tu env: GEMINI_API_KEYS (ngan cach dau phay/xuong dong, toi da
// 10, trung thi bo). Thieu thi lui ve GEMINI_API_KEY cu = pool 1 key.
function parseKeyPool(env) {
  const raw = (env.GEMINI_API_KEYS || "").trim();
  let parts = [];
  if (raw) {
    parts = raw.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
  } else {
    const single = (env.GEMINI_API_KEY || "").trim();
    if (single) parts = [single];
  }
  const seen = new Set();
  const pool = [];
  for (const k of parts) {
    if (seen.has(k)) continue;
    seen.add(k);
    pool.push(k);
    if (pool.length >= MAX_GEMINI_KEYS) break;
  }
  return pool;
}

const BANNED = [
  "shill", "spam", "fake engagement", "fake follower", "fake review",
  "money mule", "mule account", "laundering", "gambling", "betting",
  "casino", "captcha farm", "captcha solving", "airdrop farm",
  "pump and dump", "paid retweet farm",
  "generate gmv", "qualifying gmv", "fake volume", "wash trading", "wash trade",
  "simulated volume", "bot traffic", "fake traffic",
];

const ASK_MONEY_EN = "Hi! I'm interested in this bounty and I'd like to start soon. Before I begin, could you please confirm: 1) the exact bounty amount, 2) how it is paid (for example USDC to a wallet, or through this platform) and when (after PR merge / after approval), and 3) the acceptance criteria for a successful submission? Thank you!";

function log(msg) {
  console.log("[PH " + new Date().toISOString() + "] " + msg);
}

function extractBudget(title) {
  if (title.toLowerCase().includes("credit")) {
    return { budget: null, note: "site credit (khong phai tien mat/USDC)" };
  }
  let m = title.match(/\$\s?(\d[\d,]*(?:\.\d+)?)/);
  if (m) return { budget: parseFloat(m[1].replace(/,/g, "")), note: "ghi tren bai dang" };
  m = title.match(/(\d[\d,]*(?:\.\d+)?)\s?(USDC|USDT|USD)\b/i);
  if (m) return { budget: parseFloat(m[1].replace(/,/g, "")), note: "ghi tren bai dang" };
  return { budget: null, note: "" };
}

function cleanGate(text) {
  const low = (text || "").toLowerCase();
  return BANNED.filter((w) => low.includes(w));
}

// "site credit" = tra bang tin dung noi bo cua san, KHONG phai tien that ->
// bo qua ngay tai cong loc: khong tinh new_clean, khong goi Gemini, khong
// gui Telegram (dong bo luat tool local: site credit khong phai tien).
function isSiteCredit(text) {
  return (text || "").toLowerCase().includes("site credit");
}

// Cong chan REPO BAY BOT (dong bo doer.py + hunter.py): owner/ten repo chua
// "trap"/"honeypot"/"benchmark" = bay du bot san bounty -> bo qua han,
// khong vao queue, khong bao Telegram.
const TRAP_MARKERS = ["trap", "honeypot", "benchmark"];
function isTrapRepo(repo) {
  const low = (repo || "").toLowerCase();
  return TRAP_MARKERS.some((m) => low.includes(m));
}

async function fetchBounties(report) {
  const items = [];
  const seenUrl = new Set();
  const perRepo = {};
  // Xoay vong theo tick: 1 phut cron = 1 tap truy van (chi so theo phut UTC).
  const setIdx = Math.floor(Date.now() / 60000) % QUERY_SETS.length;
  const activeSet = QUERY_SETS[setIdx];
  report.query_set = setIdx;
  log("Tap truy van tick nay: #" + setIdx + " (" + activeSet.length + " truy van)");
  for (const entry of activeSet) {
    const q = entry.q;
    const url = "https://api.github.com/search/issues?q=" + encodeURIComponent(q)
      + "&sort=created&order=desc&per_page=" + PER_PAGE;
    try {
      const resp = await fetch(url, { headers: { "User-Agent": "pepper-hunter-worker/1.0", "Accept": "application/vnd.github+json" } });
      if (resp.status === 403 || resp.status === 429) {
        // Rate limit cua IP egress dung chung: ghi nhan roi bo qua em truy
        // van nay; tick sau (tap ke) chay tiep, khong lam chet vong.
        report.errors.push("GitHub search '" + q + "' rate-limit (HTTP " + resp.status + ") - bo qua");
        log("GitHub rate-limit (HTTP " + resp.status + ") o '" + q + "' - bo qua truy van nay");
        continue;
      }
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const data = await resp.json();
      for (const it of data.items || []) {
        if (it.pull_request) continue;
        const html = it.html_url || "";
        if (!html || seenUrl.has(html)) continue;
        const title = (it.title || "").trim();
        if (title.length < 6) continue;
        let repo = "";
        const ru = it.repository_url || "";
        if (ru.includes("/repos/")) repo = ru.split("/repos/")[1];
        if ((perRepo[repo] || 0) >= MAX_PER_REPO) continue;
        if (isTrapRepo(repo)) {
          log("BO QUA repo bay bot (" + repo + "): " + title.slice(0, 70));
          continue;
        }
        perRepo[repo] = (perRepo[repo] || 0) + 1;
        seenUrl.add(html);
        const b = extractBudget(title);
        items.push({
          title, url: html, repo,
          number: it.number,
          created_at: (it.created_at || "").slice(0, 10),
          excerpt: (it.body || "").replace(/\s+/g, " ").slice(0, 600),
          budget_usd: b.budget, budget_note: b.note,
        });
      }
      log("GitHub query '" + q + "': tich luy " + items.length + " ung vien");
    } catch (e) {
      report.errors.push("GitHub search '" + q + "' loi: " + e.message);
      log("LOI nguon GitHub (" + q + "): " + e.message);
    }
  }
  return items;
}

// 1 lan goi Gemini (1 key x 1 model). Tra { text, status, detail };
// status = HTTP code, null neu loi mang/khong phai HTTP.
async function geminiCallOnce(key, model, prompt) {
  let url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent";
  const headers = { "Content-Type": "application/json" };
  if (String(key).startsWith("AQ")) {
    url += "?key=" + encodeURIComponent(key);
  } else {
    headers["x-goog-api-key"] = key;
  }
  try {
    const resp = await fetch(url, {
      method: "POST", headers,
      body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }),
    });
    if (!resp.ok) {
      let detail = "";
      try { detail = (await resp.json()).error.message.slice(0, 160); } catch (e) { /* bo qua */ }
      return { text: "", status: resp.status, detail };
    }
    const data = await resp.json();
    return { text: data.candidates[0].content.parts[0].text, status: 200, detail: "" };
  } catch (e) {
    return { text: "", status: null, detail: e.message };
  }
}

// Xoay POOL key giong tool local. poolState giu trong 1 vong chay:
//   { deadKeys: Set(idx), goneModels: Map(idx -> Set(model)) }
// - 429 (het quota): chuyen model ke cua CUNG key; het model -> sang key ke.
// - 404 model: bo qua model do cho key do trong ca vong chay.
// - 400/401/403 (key chet): bo han key do trong ca vong chay.
// Thanh cong: ghi log key index + model (chi so thu tu, khong in key).
// Tra { text, keyIndex (1-based, 0 = khong co), model, error }.
async function geminiGeneratePool(pool, poolState, prompt) {
  let lastErr = "";
  for (let ki = 0; ki < pool.length; ki++) {
    if (poolState.deadKeys.has(ki)) continue;
    if (!poolState.goneModels.has(ki)) poolState.goneModels.set(ki, new Set());
    const gone = poolState.goneModels.get(ki);
    let keyDead = false;
    for (const model of GEMINI_MODELS) {
      if (gone.has(model)) continue;
      const r = await geminiCallOnce(pool[ki], model, prompt);
      if (r.text) {
        log("Gemini OK: key #" + (ki + 1) + " model " + model);
        return { text: r.text, keyIndex: ki + 1, model, error: "" };
      }
      lastErr = "key #" + (ki + 1) + " " + model + " HTTP " + r.status + " " + r.detail;
      log("Gemini " + lastErr);
      if (r.status === 400 || r.status === 401 || r.status === 403) {
        poolState.deadKeys.add(ki);
        keyDead = true;
        log("Gemini key #" + (ki + 1) + " chet (HTTP " + r.status + ") -> bo key nay trong vong chay, sang key ke");
        break;
      }
      if (r.status === 404) {
        gone.add(model);
        log("Gemini key #" + (ki + 1) + " model " + model + " 404 -> bo qua model nay cho key nay");
        continue;
      }
      if (r.status === 429) {
        log("Gemini key #" + (ki + 1) + " het quota o " + model + " (429) -> chuyen model ke cua cung key");
        continue;
      }
      // Loi khac (5xx / mang): thu model ke, khong giet vong chay.
    }
    if (!keyDead) log("Gemini key #" + (ki + 1) + " het model kha dung -> sang key ke");
  }
  return { text: "", keyIndex: 0, model: "", error: lastErr };
}

function templatePack(item) {
  const lines = [
    "# Work pack (template offline - Worker chua dung duoc Gemini)",
    "",
    "- Keo: " + item.title,
    "- San: GitHub - " + item.repo,
    "- Link: " + item.url,
    "- Ngan sach: " + (item.budget_usd ? "$" + item.budget_usd : "CHUA GHI tren bai dang"),
    "",
    "## Yeu cau (trich bai dang)",
    item.excerpt || "(bai dang khong co mo ta)",
    "",
  ];
  if (!item.budget_usd) {
    lines.push("## BAT BUOC: hoi ro tien truoc khi lam", "", "```", ASK_MONEY_EN, "```", "");
  }
  lines.push("## Ke hoach lam",
    "1. Doc ky issue + repo. 2. Comment nhan viec, cho xac nhan neu can. 3. Fork, branch rieng, lam + tu test. 4. Mo PR ghi 'Closes #" + item.number + "'. 5. Cho merge + xac nhan tra thuong.", "");
  return lines.join("\n");
}

async function geminiPack(pool, poolState, item) {
  const prompt = "Ban la tro ly chuan bi 'work pack' cho freelancer Viet Nam lam 1 keo GitHub bounty SACH.\n"
    + "Keo: " + item.title + "\nRepo: " + item.repo + "\nLink: " + item.url + "\n"
    + "Ngan sach trich tu title: " + (item.budget_usd ? "$" + item.budget_usd : "CHUA GHI") + "\n"
    + "Mo ta: " + (item.excerpt || "(khong co mo ta)") + "\n"
    + "Viet tieng Viet, ngan gon: 1) Tom tat yeu cau; 2) Ke hoach tung buoc + cach tu kiem tra; "
    + "3) Khung deliverable; 4) Diem chua ro can hoi lai."
    + (item.budget_usd ? "" : " Vi ngan sach CHUA GHI: chen mau comment tieng Anh hoi ro so tien, cach tra va tieu chi nghiem thu - bat buoc hoi truoc khi lam.");
  const g = await geminiGeneratePool(pool, poolState, prompt);
  if (!g.text) {
    log("Gemini: tat ca key deu fail (loi cuoi: " + g.error + ") -> template offline");
    return { pack: templatePack(item), mode: "template (tat ca key Gemini deu fail: " + g.error + ")" };
  }
  return { pack: "# Work pack (Gemini soan)\n\n- Keo: " + item.title + "\n- Link: " + item.url + "\n\n---\n\n" + g.text, mode: "gemini (key #" + g.keyIndex + ", " + g.model + ")" };
}

async function telegramSend(token, chatId, text) {
  try {
    const resp = await fetch("https://api.telegram.org/bot" + token + "/sendMessage", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ chat_id: chatId, text: text.slice(0, 3900) }),
    });
    const data = await resp.json();
    return { ok: !!data.ok, error: data.ok ? "" : JSON.stringify(data).slice(0, 200) };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

async function runHunt(env) {
  const report = { at: new Date().toISOString(), fetched: 0, processed: 0, new_clean: [], dirty: 0, skipped_site_credit: 0, notified: 0, kv_writes: 0, errors: [], config: {} };
  const geminiPool = parseKeyPool(env);
  const poolState = { deadKeys: new Set(), goneModels: new Map() };
  const cleanDeals = [];
  const tgToken = (env.TELEGRAM_BOT_TOKEN || "").trim();
  const tgChat = (env.TELEGRAM_CHAT_ID || "").trim();
  report.config = { gemini: geminiPool.length > 0, gemini_keys: geminiPool.length, telegram: !!(tgToken && tgChat), kv: !!env.SEEN };
  if (!geminiPool.length) log("chua cau hinh: GEMINI_API_KEYS / GEMINI_API_KEY (Worker secret) - dung template offline");
  else log("Gemini pool: " + geminiPool.length + " key (xoay vong, toi da " + MAX_GEMINI_KEYS + ")");
  if (!tgToken || !tgChat) log("chua cau hinh: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (Worker secret) - khong gui Telegram");
  if (!env.SEEN) {
    report.errors.push("chua cau hinh: KV binding SEEN - khong chong trung duoc, dung vong nay");
    log("chua cau hinh: KV binding SEEN -> dung vong nay");
    return report;
  }

  // Ghi KV qua 1 cua duy nhat de DEM so lan ghi (KV free gioi han ~1000 lan
  // ghi/ngay; ghi vo dieu kien queue + run:last moi tick tung lam vo tran
  // 10/11). Loi ghi (ke ca het quota) chi log + ghi vao errors, KHONG lam
  // chet vong chay.
  async function kvPut(key, value) {
    try {
      await env.SEEN.put(key, value);
      report.kv_writes += 1;
      return true;
    } catch (e) {
      log("LOI ghi KV " + key + ": " + e.message);
      report.errors.push("ghi KV " + key + " loi: " + e.message);
      return false;
    }
  }

  const items = await fetchBounties(report);
  report.fetched = items.length;
  log("Tim thay " + items.length + " ung vien tho tu GitHub");

  for (const it of items) {
    if (report.processed >= MAX_NEW_PER_RUN) break;
    const seenBefore = await env.SEEN.get("url:" + it.url);
    if (seenBefore) continue;
    const hits = cleanGate(it.title + " " + (it.excerpt || ""));
    // Danh dau seen: chi xay ra voi muc MOI that su duoc xu ly (toi da
    // MAX_NEW_PER_RUN/vong) - day la ghi theo su kien, khong phai ghi moi tick.
    await kvPut("url:" + it.url, new Date().toISOString());
    report.processed += 1;
    if (hits.length) {
      report.dirty += 1;
      log("LOAI BAN (" + hits.join(", ") + "): " + it.title.slice(0, 70));
      continue;
    }
    if (isSiteCredit(it.title + " " + (it.excerpt || ""))) {
      report.skipped_site_credit += 1;
      log("bo qua: site credit, khong phai tien that: " + it.title.slice(0, 70));
      continue;
    }
    let packInfo;
    if (geminiPool.length) {
      packInfo = await geminiPack(geminiPool, poolState, it);
    } else {
      packInfo = { pack: templatePack(it), mode: "template (chua co Gemini key)" };
    }
    const rec = { title: it.title, repo: it.repo, url: it.url, budget_usd: it.budget_usd, pack_mode: packInfo.mode };
    report.new_clean.push(rec);
    cleanDeals.push({
      title: it.title, url: it.url, budget_usd: it.budget_usd, pack_mode: packInfo.mode,
      pack: (packInfo.pack || "").slice(0, 6000),
    });
    log("KEO THAT MOI (SACH): " + it.title.slice(0, 70) + " | pack: " + packInfo.mode);
    if (tgToken && tgChat) {
      const msg = "[Pepper Hunter] KEO THAT MOI - SACH\n" + it.title
        + "\nSan: GitHub " + it.repo
        + "\nNgan sach: " + (it.budget_usd ? "$" + it.budget_usd : "chua ghi tren bai dang")
        + "\nLink: " + it.url
        + "\n\n--- Work pack (" + packInfo.mode + ") ---\n" + packInfo.pack;
      const sent = await telegramSend(tgToken, tgChat, msg);
      if (sent.ok) report.notified += 1;
      else report.errors.push("Telegram loi (" + it.title.slice(0, 40) + "): " + sent.error);
    }
  }
  // Hang doi TICH LUY cho doer: APPEND keo sach moi vao KV "queue"
  // (dedupe theo url, cap 100, giu moi nhat). run:last chi giu 1 vong nen
  // tung lam troi keo khi doer chua kip doc - queue la noi doer bat lai.
  let queue = [];
  try {
    const rawQ = await env.SEEN.get("queue");
    if (rawQ) {
      const parsed = JSON.parse(rawQ);
      if (Array.isArray(parsed)) queue = parsed;
    }
  } catch (e) { queue = []; }
  const qUrls = new Set(queue.map((d) => d.url));
  let appended = 0;
  for (const d of cleanDeals) {
    if (!qUrls.has(d.url)) {
      queue.push({ title: d.title, url: d.url, budget_usd: d.budget_usd, pack_mode: d.pack_mode, pack: d.pack, ts: report.at });
      qUrls.add(d.url);
      appended += 1;
    }
  }
  if (queue.length > 100) queue = queue.slice(queue.length - 100);
  // Chi ghi queue khi that su co keo moi duoc them (truoc day ghi MOI tick =
  // ~1440 lan/ngay, vuot han muc ghi KV free 1000/ngay).
  if (appended > 0) {
    await kvPut("queue", JSON.stringify(queue));
  }
  report.queue_size = queue.length;
  // run:last cho tang TU LAM (doer) doc qua GET /latest: chi ghi khi co keo
  // sach moi (noi dung thay doi that) hoac heartbeat thua ~15 tick/lan (phut
  // 0/15/30/45) de /latest van co dau thoi gian tuoi. Tick yen tinh khong ghi.
  const heartbeatTick = new Date().getMinutes() % 15 === 0;
  if (cleanDeals.length > 0 || heartbeatTick) {
    await kvPut("run:last", JSON.stringify({
      ts: report.at,
      fetched: report.fetched,
      new_clean: report.new_clean.length,
      skipped_site_credit: report.skipped_site_credit,
      dirty: report.dirty,
      kv_writes: report.kv_writes + 1,
      deals: cleanDeals,
    }));
  }
  log("Xong vong: xu ly " + report.processed + " moi, sach " + report.new_clean.length
    + ", ban " + report.dirty + ", bo qua site credit " + report.skipped_site_credit
    + ", da bao Telegram " + report.notified + ", ghi KV " + report.kv_writes + " lan");
  return report;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/latest") {
      let last = { ts: null, deals: [] };
      let queue = [];
      if (env.SEEN) {
        try {
          const raw = await env.SEEN.get("run:last");
          if (raw) last = JSON.parse(raw);
        } catch (e) { /* tra mac dinh */ }
        try {
          const rawQ = await env.SEEN.get("queue");
          if (rawQ) {
            const parsed = JSON.parse(rawQ);
            if (Array.isArray(parsed)) queue = parsed;
          }
        } catch (e) { /* queue rong */ }
      }
      return new Response(JSON.stringify({ ...last, queue }),
        { headers: { "Content-Type": "application/json; charset=utf-8" } });
    }
    if (url.pathname === "/run") {
      const report = await runHunt(env);
      return new Response(JSON.stringify(report, null, 1), { headers: { "Content-Type": "application/json; charset=utf-8" } });
    }
    if (url.pathname === "/") {
      return new Response(JSON.stringify({
        ok: true, service: "pepper-hunter",
        role: "runner chinh - cron moi phut (* * * * *)",
        time: new Date().toISOString(),
        config: {
          gemini: parseKeyPool(env).length > 0,
          gemini_keys: parseKeyPool(env).length,
          telegram: !!((env.TELEGRAM_BOT_TOKEN || "").trim() && (env.TELEGRAM_CHAT_ID || "").trim()),
          kv_seen: !!env.SEEN,
        },
        hint: "GET /run de chay thu 1 vong ngay",
      }, null, 1), { headers: { "Content-Type": "application/json; charset=utf-8" } });
    }
    return new Response("not found", { status: 404 });
  },

  async scheduled(event, env, ctx) {
    log("Cron kich hoat: " + (event.cron || ""));
    ctx.waitUntil(runHunt(env));
  },
};
