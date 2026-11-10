<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->

# Don xin nhan viec (APPLY) - [Challenge] Capability manifest never advertises a non-routable adapter as supported

- Keo: [Challenge] Capability manifest never advertises a non-routable adapter as supported
- Link: https://github.com/Conxian/conxian-gateway/issues/828
- Mode: cho_duoc_chon
- Nguon soan: gemini (key #1, gemini-3.5-flash-lite)
- Trang thai gui: CHO PAT - chua gui

## Noi dung comment se gui

Hi, I'm PepperResearch, experienced in Rust backend development and API validation logic. I would love to take on this challenge.

Here is my plan to tackle this issue:
1. Review the codebase around `internal/api/src/capabilities.rs` (`classify`) and `internal/api/src/lib.rs` to understand how adapter capabilities and taxonomy bindings are currently mapped.
2. Set up a local test environment to reproduce the behavior when using an unmapped adapter ID (like `bitvm3`).
3. Develop a targeted integration test or command transcript that asserts `operation_classes == ["unavailable"]` for non-routable adapters, or search for a counterexample.
4. Verify the test passes locally against the `main` branch code path without editing the manifest.
5. Submit the reproduction artifact via a PR.

ETA: [X] days.

Could you please assign this issue to me? Before I begin, could you please confirm: 1) the exact bounty amount, 2) how it is paid (for example USDC to a wallet, or through this platform) and when (after PR merge / after approval), and 3) the acceptance criteria for a successful submission? Thank you!
