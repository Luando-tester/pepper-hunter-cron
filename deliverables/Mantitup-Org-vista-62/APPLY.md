<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->

# Don xin nhan viec (APPLY) - Bug: vista deploy still breaks static hosts and platform adapters

- Keo: Bug: vista deploy still breaks static hosts and platform adapters
- Link: https://github.com/Mantitup-Org/vista/issues/62
- Mode: cho_duoc_chon
- Nguon soan: gemini (key #1, gemini-3.5-flash-lite)
- Trang thai gui: se gui bang GITHUB_PAT ngay sau khi luu

## Noi dung comment se gui

Hi, I'm PepperResearch, an experienced developer with strong expertise in CLI tooling, build pipelines, and multi-platform deployment adapters (Vercel, Cloudflare Pages, Netlify, and Docker).

Here is my plan to tackle this issue:
1. Scaffold a fresh reproduction app using `create-vista-app` and run a dry-run build to inspect emitted platform files (`wrangler.toml`, Dockerfile, etc.).
2. Fix the Cloudflare Pages `/rsc/*` routing rule and `_redirects` generation to prevent Flight payload rewrites.
3. Fix the PPR shell leak and ensure standalone `.vista/standalone/server.js` bundles correctly for Vercel/Netlify and Render.
4. Verify correct target detection between static Pages and containers, ensuring correct `CMD` / `startCommand` emission.
5. Validate against the pass criteria using local dry-runs and live testing against `vistajs.pages.dev`.

**ETA:** 3 days.

Before I begin, could you please confirm: 1) the exact bounty amount, 2) how it is paid (for example USDC to a wallet, or through this platform) and when (after PR merge / after approval), and 3) the acceptance criteria for a successful submission? Thank you!

Please assign this issue to me so I can get started.
