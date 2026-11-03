# S0-GPU report (2026-11-03)

**Run:** five pods, one per model, on RTX PRO 6000 Blackwell (driver 595.91.07, compute capability 12.0). Pipeline
**v1.3.0** (`37031bcd`), Missing Piece at `cf8a376`.
- Raw results are in the artifacts dataset `RandallSPQR/stpt-gate-artifacts`, under `missing-piece/S0/<run>/<model>/`.
- The analysis is `gates/S0/gpu/analyse.py`. Numbers below are read from `gates/S0/gpu/results/s0_gpu_results.json`
  (file sha256s of every input listed there).
- **Spend:** about 6.6 pod-hours, about **$16.60**, within the approval. One stuck pod was replaced after 6 minutes;
  three pods were stopped early (below).
- **Rules:** fixed before any call (`gates/S0/S0_GPU_PLAN.md`, `gates/S0/serving_check.py`) and applied as written.

## Part 1: pinned stack and serialisation on the box: PASS for all five models

| model | weight_hash vs pin | token-level agreement (all MP context shapes) | A/B single tokens | stop ids | 8 repeats bit-identical (3 multi-turn vote prompts) | exact fallback | non-A/B mass |
|---|---|---|---|---|---|---|---|
| Llama-3.1-8B | ok | 55/55 | yes | ok | yes | ok | 0.0000 |
| Gemma-2-9B | ok | 55/55 | yes | ok | yes | ok | ≤ 0.0009 |
| Qwen3.5-9B | ok | 55/55 | yes | ok | yes | ok | ≤ 0.0015 |
| Gemma-3-27B | ok | 55/55 | yes | ok | yes | ok | 0.0000 |
| Qwen3.5-27B | ok | 55/55 | yes | ok | yes | ok | ≤ 0.0002 |

- **Stack:** Python 3.11.13, vLLM 0.19.1, torch 2.10.0+cu128, transformers 5.5.3 (serving); pipeline 1.3.0 (client).
- **Measured strict speed** (batch size 1, prefix cache off; 4 rounds, probes on): 42 / 112 / 50 / 154 / 143 s per game
  (Llama / Gemma-2 / Qwen-9B / Gemma-3 / Qwen-27B). That is **502 s per game across the five models**, against the
  ~410 s the S6 cost model assumed. Gemma-2 is the outlier: 112 s for a 9B model.

**Link check (optional; informative only).** Missing Piece read StPT's three S0 prompts under v1.3.0 strict and compared
them with StPT's recorded v1.2.0 S0 readouts (same GPU type and driver, a different pod and day):
- **Llama and Gemma-2:** bit-identical to a v1.2.0 start.
- **Qwen3.5-9B and Qwen3.5-27B:** within v1.2.0's own restart range (0.001 and 0.125 nats, against 0.12 and 0.23).
- **Gemma-3-27B:** 0.50 nats, against 0.25 between StPT's two recorded starts.
  - Gemma-3 is the model with the largest drift between starts (StPT S4, A16: discrete start states), and the reference
    has only two starts.
  - The strict commands are byte-identical (CPU link check), so this most likely reflects Gemma-3's start-state spread,
    not a version difference.
  - The formal link check (alternating v1.2.0 and v1.3.0 starts in one pod) was not run.

## Part 2: serving modes. Result: NO MODE VALIDATED under the pre-stated rules

| mode | model | C1 caching, cold vs warm (max nats; share > 0.05) | C2 batching, alone vs cohort of 32 | C3 own Δ support [95% CI] (8 quads) | s/game strict → mode |
|---|---|---|---|---|---|
| throughput | Llama-3.1-8B | 0.125; 14% → **fail** | 0.250; 41% → **fail** | +0.094 [−0.055, +0.242] | 42.2 → 2.9 |
| throughput | Gemma-2-9B | 0.125; 8% → **fail** | 0.125; 22% → **fail** | +0.031 [−0.117, +0.195] | 111.6 → 14.5 |
| throughput | Gemma-3-27B | 0.375; 33% → **fail** | 0.375; 25% → **fail** | +0.055 [−0.156, +0.273] | 154.4 → 21.3 |
| throughput_invariant | Llama-3.1-8B | **0.000 → pass** | **0.000 → pass** | +0.047 [−0.172, +0.266] | 42.2 → 4.9 |
| throughput_invariant | Gemma-2-9B | **0.000 → pass** | **0.000 → pass** | +0.148 [−0.031, +0.336]; words KS p 0.006 | 111.6 → 24.6 |
| throughput_invariant | Gemma-3-27B | server **did not start**: vLLM rejects FLASH_ATTN for this multimodal checkpoint ("partial multimodal token full attention not supported") | | | |
| both | Qwen3.5-9B / 27B | **excluded: not a test of the mode** (see "Defect found") | | | |

**C3 pooled (the rule: the 95% CI includes 0 and lies inside ±0.10):**
- `throughput` (Llama, Gemma-2, Gemma-3; 24 quads): +0.060 [−0.047, +0.162]. **Fail** (upper bound).
- `throughput_invariant` (Llama, Gemma-2; 16 quads): +0.098 [−0.043, +0.246]. **Fail** (upper bound).
- Message-length KS p 0.25 and 0.31, non-A/B mass and invalid votes unchanged.
- The pooled test had 16–24 quads, not the planned 40, because the Qwen pair is excluded and Gemma-3's invariant server
  did not start. Every model-mode estimate is positive.

**Reading:**
- **Plain `throughput`** perturbs readouts by 1–3 bf16 steps on 8–41% of prompts. That is the same size as restart
  drift, but over the pre-stated share.
- **`throughput_invariant`** makes caching and batching numerically exact: Δ = 0.000 on every prompt, for both models
  that served. That settles the open hardware question: batch invariance works on sm_120 for Llama and Gemma-2.
  - Its kernels are not the strict kernels, though, so its games still diverge from strict games.
  - C3, a strict-versus-mode comparison, fails at this sample size. All its estimates point the same way.
- `serving.validated_modes` in `pins.yaml` stays empty. Every Missing Piece run uses `strict` until the owner decides
  otherwise.

## Defect found: pipeline v1.3.0's modes did not apply to the Qwen pair

- **What happened.** The Qwen3.5 profiles set `--max-num-seqs 1 --no-enable-prefix-caching` in their own
  `serve.extra_args`, and the command builder keeps a profile's flag. Under both throughput modes the Qwen pair ran
  with one sequence in flight. The vLLM log shows `Running: 1 reqs, Waiting: 27 reqs`; caching came on only because the
  mode's flag came later on the command line.
- **Fix:** proposed **v1.3.1** (`proposals/pipeline-v1.3.1/`), with tests on every model's full command and strict
  unchanged.
- **What it cost.**
  - Qwen3.5-9B's pod was stopped after its throughput phase.
  - Qwen3.5-27B's pod was stopped after its strict phase.
  - Their strict and Part 1 results are valid and kept, so a re-run needs only the modes.

## Process note (logged)

While monitoring, Missing Piece printed Llama-3.1-8B's mean receiver support by cell for its 32 strict S0 games, which
is a look at development-data cell outcomes. These games are S0 serving checks, not pilot data. To keep the look from
informing anything:
- **No S0 game counts toward the S4 pilot.** This drops the plan's option to reuse them.
- The S0 analysis reports only mode-versus-strict differences pooled over cells.

## Measured costs (feeds the S6 recompute)

At 502 s per five-model game (strict) and $2.49 per pod-hour, with model loads, about 8 starts per model at Lean:
- **Lean** (30 stories, 1 replicate): about 37 GPU-hours, about **$92** GPU, plus about $21 grading.
- **Standard** (72 stories): about 88 GPU-hours, about **$219** GPU, plus about $50 grading.

`throughput_invariant`, where it ran, was 4.5–8.6× faster.

## For the owner

1. **Serving mode for the pilot and the confirmatory run.** Under the rules as written, it is **`strict`**.
   - Alternatives, each a decision made after these results (a deviation to log):
     - (a) a larger, pooled C3 for `throughput_invariant` (with v1.3.1 for the Qwen pair, and TRITON_ATTN tried for
       Gemma-3), sized to resolve ±0.10;
     - (b) accept `throughput_invariant` on its exact C1/C2 and run every cell in it. Within-study contrasts don't need
       strict-equivalence, but the bridge with StPT (v1.2.0 strict) would then need one mode for both arms (D41).
   - **Recommendation:** stay `strict`. At Lean the saving is roughly $60–75 and at Standard roughly $150–170 (assumed speed-ups for
     the models not measured), and strict keeps the rules intact.
2. **Pipeline v1.3.1.** Tag it only if (a) is wanted. Strict serving is identical under v1.3.0 and v1.3.1.
3. **Message band (for S4).** In-band shares were 0.73 / 0.94 / 0.26 / 0.62 / 0.65. The 60–120-word instruction needs
   revision before the pilot.
