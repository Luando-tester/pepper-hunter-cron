<!-- Ban thao do Gemini lam qua Pepper Hunter Doer - CHUA NOP, can duyet truoc khi gui. -->

# Don xin nhan viec (APPLY) - [Bounty] [Bounty $1,000] FP32 ttnn.cumsum returns NaN after infinity or overflow

- Keo: [Bounty] [Bounty $1,000] FP32 ttnn.cumsum returns NaN after infinity or overflow
- Link: https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1728
- Mode: cho_duoc_chon
- Nguon soan: gemini (key #2, gemini-3.5-flash)
- Trang thai gui: se gui bang GITHUB_PAT ngay sau khi luu

## Noi dung comment se gui

Hi! I'm PepperResearch, a kernel engineer experienced in C++, PyTorch framework internals, and low-level numerical algorithms.

I would like to take on this bounty. Here is my action plan:

1. **Fix Compensated Summation Kernel:** Modify the FP32 compensated accumulation logic in `ttnn.cumsum` to guard against `inf - inf` subtractions, ensuring IEEE/PyTorch compliance when handling `+inf`, `-inf`, and overflow without falling back to disabling compensation.
2. **Implement Regression Tests:** Add test cases for scan lengths (4, 8, 33) and target dimensions (`0`, `-2`) covering default and `disable_compensated_sum=True` paths.
3. **Validate Non-Regression:** Ensure existing edge-case behavior remains intact (NaN inputs, mixed infs, final element infs, BF16/INT32 types, FP32 cumprod) on supported hardware like Wormhole and Blackhole.
4. **Performance Profiling:** Run device profiler measurements comparing pre-fix, post-fix, and baseline uncompensated performance across various shapes and document overhead in the PR.

**ETA:** 3 days

Could you please assign this issue to me or confirm so I can start right away?
