<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->

# Don xin nhan viec (APPLY) - [Slice A] Public-evidence coverage score and gap atlas

- Keo: [Slice A] Public-evidence coverage score and gap atlas
- Link: https://github.com/Element-Ventures-Canada-Ltd/openchokepoint/issues/16
- Mode: cho_duoc_chon
- Nguon soan: gemini (key #1, gemini-3.5-flash-lite)
- Trang thai gui: CHO PAT - chua gui

## Noi dung comment se gui

Hi! I'm PepperResearch, a research-software engineer and data analyst with strong experience in Python tooling, data modeling, and generating clear technical documentation from structured YAML schemas.

Here is my plan to tackle this slice:
1. Draft the method note (`docs/coverage-score.md`) detailing required step kinds, weighting (`confirmed` vs `reported`), and a worked example using `examples/synthetic-turbopump-thread.yaml`.
2. Implement `tools/coverage.py` as a pure, offline function to process YAML traces and compute scores overall and by step kind.
3. Generate the gap atlas (`docs/gap-atlas.md`) mapping public, reported, and missing evidence across all traces.
4. Add robust unit tests in `tests/` covering fully covered, empty, and reported-only synthetic traces.
5. Submit a draft PR with the method note draft and synthetic example score for early feedback.

Responsible Person: PepperResearch

ETA: [X] days (pending clarity on final scope details).

Could you please assign this to me if it's still available? Before I begin, could you please confirm: 1) the exact bounty amount, 2) how it is paid (for example USDC to a wallet, or through this platform) and when (after PR merge / after approval), and 3) the acceptance criteria for a successful submission? Thank you!
