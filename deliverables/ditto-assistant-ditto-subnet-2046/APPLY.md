<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->

# Don xin nhan viec (APPLY) - Implement bounty acceptance, alpha awards, fee refunds and accounting

- Keo: Implement bounty acceptance, alpha awards, fee refunds and accounting
- Link: https://github.com/ditto-assistant/ditto-subnet/issues/2046
- Mode: cho_duoc_chon
- Nguon soan: gemini (key #1, gemini-3.5-flash)
- Trang thai gui: CHO PAT - chua gui

## Noi dung comment se gui

Hi team, I am PepperResearch, a software engineer with strong expertise in backend systems, transaction idempotency, deterministic ledger accounting, and secure treasury policy implementations.

Here is my proposed implementation plan:
1. **Audit & Salvage**: Review and salvage reusable canonical-JSON and receipt data structures from reference PR #2097, replacing its in-memory storage with durable state management and strict operator authority validation.
2. **Obligation & Award Logic**: Build data models and state tracking for single/shared alpha awards, full entry-fee refunds upon acceptance, retained fee accounting, and explicit operator-approved obligation bounds.
3. **Idempotency & Security**: Implement durable transactional idempotency across retries, duplicated PRs, key rotations, and transfer reconciliations, while keeping private Jira/source context unexposed.
4. **Testing & Verification**: Create extensive test suites matching all issue acceptance criteria (shared splits, reviewer delays, failed/uncertain transfers, duplicate payment prevention) in a rehearsal mode without live funds.

**Estimated ETA**: 3 days after assignment.

Please assign this issue to me or confirm if I can get started.

Before I begin, could you please confirm: 1) the exact bounty amount, 2) how it is paid (for example USDC to a wallet, or through this platform) and when (after PR merge / after approval), and 3) the acceptance criteria for a successful submission? Thank you!
