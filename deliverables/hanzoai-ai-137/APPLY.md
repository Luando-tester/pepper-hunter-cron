<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->

# Don xin nhan viec (APPLY) - [QA Bounty] [P0] Model Routing & Failover

- Keo: [QA Bounty] [P0] Model Routing & Failover
- Link: https://github.com/hanzoai/ai/issues/137
- Mode: cho_duoc_chon
- Nguon soan: gemini (key #1, gemini-3.5-flash-lite)
- Trang thai gui: CHO PAT - chua gui

## Noi dung comment se gui

Hi! I'm PepperResearch, experienced in QA automation, API reliability testing, and LLM gateway failure modes. 

Here is my plan to tackle this QA bounty:
1. Set up a comprehensive test harness targeting the `/v1/models` catalog to verify exact backend routing and detect any silent substitutions or alias misdirections.
2. Simulate upstream failures (timeouts, rate limits `429`, and `5xx` errors) to rigorously test automatic failover and fallback chains while ensuring request parameters (tools, streaming, system prompts) are fully preserved.
3. Validate response metadata (model fields, provider headers, and latency) and check for edge cases like silent `200 OK` empty responses or truncated streams.
4. Deliver a reproducible automated test suite along with a detailed QA report featuring full request/response traces (and fixes via PR if applicable).

**ETA:** [X] days (ready to start immediately upon confirmation).

Please assign this issue to me so I can get started. Before I begin, could you please confirm: 1) the exact bounty amount, 2) how it is paid (for example USDC to a wallet, or through this platform) and when (after PR merge / after approval), and 3) the acceptance criteria for a successful submission? Thank you!
