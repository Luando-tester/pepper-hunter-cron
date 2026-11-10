<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->

# Don xin nhan viec (APPLY) - [Challenge] Independently review the release-signing design and the ceremony invite

- Keo: [Challenge] Independently review the release-signing design and the ceremony invite
- Link: https://github.com/Conxian/conxius-enclave-sdk/issues/726
- Mode: cho_duoc_chon
- Nguon soan: gemini (key #2, gemini-3.6-flash)
- Trang thai gui: se gui bang GITHUB_PAT ngay sau khi luu

## Noi dung comment se gui

Hi maintainers, I am interested in taking on this independent review challenge, bringing solid expertise in Rust code auditing, threshold cryptography (FROST), and security design analysis.

Here is my proposed plan to review the release-signing design and signing paths:

1. **Audit Ceremony & Invite Documentation**: Review `THRESHOLD_DKG_CEREMONY.md` and `JOIN_THE_CEREMONY.md` for operational edge cases, secret leakage, or missing independence checks.
2. **Evaluate Attestation Design**: Analyze `THRESHOLD_ATTESTATION_DESIGN.md` for proof schema soundness, nonce handling, replay vulnerabilities, and revocation gaps.
3. **Inspect Core Code Implementation**: Audit `src/enclave/threshold.rs` and `src/signing/threshold.rs` to verify signature binding correctness and state machine invariants.
4. **Report & Format Findings**: Compile reproducible defects or unsound claims with concrete failing examples following `PROOF_GUILD_CHALLENGE_FORMAT.md`.

Estimated ETA: 3 days from assignment.

Before I begin, could you please confirm: 1) the exact bounty amount, 2) how it is paid (for example USDC to a wallet, or through this platform) and when (after PR merge / after approval), and 3) the acceptance criteria for a successful submission? Thank you!

Please assign this issue to me or confirm if I may proceed.
