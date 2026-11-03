# S6 cost model: what was assumed, and a recompute (2026-11-03; revised for P13 and the Paper 1 graders)

**Owner's question: did S6 assume batched or sequential calls?** **Sequential.**

S6 as filed (`S6_REPORT.md`, `power_sim.py COST`) assumed:
- batch size 1, one call at a time, with prefix caching off, as pipeline v1.2.0 serves;
- assumed token counts of 90,000 prefill and 3,400 decoded tokens per game;
- probes for all five agents after every round;
- an Opus 5.5 grader on every game.

None of these cost inputs was measured.

**Re-run:** `python gates/S6/cost_model.py`. Results are in `results/cost_model.json` and `results/cost_model.md`.

## Part A: measured on CPU (token counts of real Missing Piece contexts)

- **Games:** 32 development games per variant, built by the real engine (4 rounds; messages of 80–110 words, mean
  94.9; exit polls of 20–35 words).
- **Tokenisation:** each request is serialised by the pipeline's `qwen3_5` serializer and tokenised by the pinned
  Qwen3.5 tokenizer. Its tokenizer.json sha256 begins `5f9e4d4901a92b99`, matching the pipeline's recorded provenance.
- **Prefix-cache hits:** simulated as vLLM's automatic prefix caching works. Full 16-token blocks of the longest prefix
  shared with an earlier request's prompt plus output, in submission order, are reused.

| variant | prompt tokens / game | prompt tokens computed / game | output tokens / game | calls / game |
|---|---|---|---|---|
| S6 as filed (probes: all agents, every round) | 120,853 | 120,853 | 2,787 | 55 |
| new probes (receivers at rounds 2 and 4, speaker at round 4: P13) | 101,843 | 101,843 | 2,776 | 44 |
| new probes + prefix caching | 101,843 | **17,614** | 2,776 | 44 |

**Readings:**
- S6 under-assumed prefill: 121k measured against 90k assumed.
- The new probe policy cuts prompt tokens by 16% and calls by 20%.
- Prefix caching removes **83%** of the prompt computation.

At batch size 1, decode dominates GPU time: about 31 s of the 46 s a small-model game takes. **Caching alone therefore
saves about a fifth of GPU time. Batching is the large lever**, because it shares decode steps across sequences in
flight.

## Part B: GPU time (ASSUMED rates; the S4 pilot measures them)

**Assumptions:**
- Sequential throughput as S6: 90 / 30 decoded tok/s and 8,000 / 2,500 prefill tok/s for small / 27B models.
- Batched: lockstep cohorts of ≥ 16 in flight, with aggregate decode speedup 5× / 8× / 12× (low / mid / high).
- Batch-invariant kernels at 0.4 / 0.6 / 0.8 of the non-invariant throughput.
- $2.49 per pod-hour; 8 quads per server start.

## Measured in S0-GPU (2026-11-03; `gates/S0/S0_GPU_REPORT.md`)

- **Strict serving**, the only validated mode: 42 / 112 / 50 / 154 / 143 s per game (Llama / Gemma-2 / Qwen-9B /
  Gemma-3 / Qwen-27B). That is **502 s per five-model game**, against about 410 s assumed in Part B.
- With loads: about **$92** GPU at Lean (30 stories) and about **$219** at Standard (72).
- **Plain `throughput`, measured:** 2.9 / 14.5 / – / 21.3 s per game. **`throughput_invariant`, measured:** 4.9 /
  24.6 s for Llama and Gemma-2. Neither mode is validated (C3 fails).

## Part C: grading (Paper 1's graders via OpenRouter, owner 2026-11-03)

Verified against RandallSPQR/edsl_wwil @ `35ffd5dc`, `data/perfect_lie/models.json`:
- **Primary:** `anthropic/claude-sonnet-4.5` ($3 / $15 per MTok).
- **Gate grader:** `google/gemini-2.5-flash` ($0.30 / $2.50), on the **same** items. Paper 1's agreement gate is
  computed on "primary versus Google on every lie".
- Both non-thinking, at temperature 0.
- **No batch discount:** OpenRouter has no batch endpoint. The primary's rubric is a cached prefix; the gate grader is
  costed uncached.
- **Coverage:** speaker messages on every quad (P14); verifier messages and exit polls on the 50% quad subsample. That
  is about 7.5 graded items per game.

**Grading cost: about $0.017 per game** ($0.040 if the rubric does not cache), about the same as Opus as filed
($0.018). The savings from Sonnet's lower price are spent on:
- the second grader on every item, which Paper 1's gate needs;
- 100% speaker coding (P14);
- the loss of the batch discount on this route.

## Total cost, one replicate, all five models (`results/cost_model.json`)

| stories | S6 as filed (re-run with measured tokens) | new probes | + prefix caching | + batched (low / mid / high) | + batched, batch-invariant (low / mid / high) |
|---|---|---|---|---|---|
| 26 | $88 (28.0 GPU h) | $84 | $70 | $37 / $33 / $32 | $53 / $39 / $33 |
| 30 (Lean) | $102 (32.3 h) | $97 | $80 | $42 / $38 / $36 | $62 / $45 / $38 |
| 72 (Standard) | $244 (77.0 h) | $231 | $192 | $100 / $91 / $86 | $147 / $106 / $91 |

**Notes:**
- "Low / mid / high" are the assumption brackets, not uncertainty intervals.
- **Under batching, grading becomes the largest line:** about $21 of $38 at 30 stories, and $50 of $91 at 72.
- **Model loading becomes a large share of GPU time:** 8 quads per start means 7–18 starts per model, at 3–8 minutes
  each. Raising quads per start under batching cuts this further. Restart drift is handled by blocking, not by frequent
  restarts.

## What happens next (owner's items 1, 2 and 5)

1. **Pipeline (D41).** Missing Piece adopts v1.3.0 once it is applied and tagged. MP S0-GPU validates the throughput
   modes (C1–C3) before any other run.
2. **The S4 pilot runs in the mode chosen for the confirmatory run**, through `mp.runner.run_lockstep`. Every call
   records server-reported prompt, cached and completion tokens, latency and cohort, plus grader usage.
   `cost_model.measured_costs()` turns these into per-game costs.
3. **S6 recompute (owner's item 5).** Before any tier or equivalence decision, the tier table is recomputed with:
   - the S4 variance components (80th percentile), which set MDE and TOST power;
   - the S4 measured per-call costs, which set GPU hours and dollars.

   The power columns of the provisional table do not change with the serving mode, the probe policy or the grader: the
   primary outcome and its estimator are untouched.
