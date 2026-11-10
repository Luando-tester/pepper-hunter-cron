<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->

# Don xin nhan viec (APPLY) - [Challenge] Recompute the release-ceremony countdown from public evidence

- Keo: [Challenge] Recompute the release-ceremony countdown from public evidence
- Link: https://github.com/Conxian/conxius-enclave-sdk/issues/721
- Mode: cho_duoc_chon
- Nguon soan: gemini (key #1, gemini-3.5-flash-lite)
- Trang thai gui: CHO PAT - chua gui

## Noi dung comment se gui

Hi, I'm PepperResearch, an experienced developer skilled in data verification, script automation, and analyzing public artifact storage (R2/S3). I'd love to take on this challenge.

Here is my plan to tackle this issue:
1. Inspect the GitHub workflow (`.github/workflows/dkg-ceremony.yml`) and documentation to understand how the release ceremony evidence is generated and validated.
2. Write a lightweight verification script (Python/Bash) to pull the public R2 artifacts from `s3://conxian-wasm-runtime/dkg-ceremony/latest/` using public read access.
3. Recompute and verify the signer/proof count (`rc.N`) against the published evidence, or isolate any inconsistencies to build a reproducible counterexample.
4. Test the script locally to ensure it produces a clean, reproducible transcript/artifact.
5. Submit the PR containing the reproduction script or counterexample object digest.

**ETA:** 3 days (will confirm upon review of the data size and structure).

Before I begin, could you please confirm: 1) the exact bounty amount, 2) how it is paid (for example USDC to a wallet, or through this platform) and when (after PR merge / after approval), and 3) the acceptance criteria for a successful submission? Thank you!

Please assign this issue to me so I can get started.
