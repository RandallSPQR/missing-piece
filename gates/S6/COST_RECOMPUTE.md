# S6 cost model: what was assumed, and a recompute (2026-11-03)

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
| new probes (receivers, rounds 2 and 4) | 98,648 | 98,648 | 2,775 | 43 |
| new probes + prefix caching | 98,648 | **18,680** | 2,775 | 43 |

**Readings:**
- S6 under-assumed prefill: 121k measured against 90k assumed.
- The new probe policy cuts prompt tokens by 18% and calls by 22%.
- Prefix caching removes **81%** of the prompt computation.

Output (decode) tokens are unchanged, and at batch size 1 decode dominates GPU time: about 31 s of the 45 s a
small-model game takes. **Caching alone therefore saves about a fifth of GPU time. Batching is the large lever**,
because it shares decode steps across sequences in flight.

## Part B: GPU time and money (ASSUMED rates; the S4 pilot measures them)

**Assumptions:**
- Sequential throughput as S6: 90 / 30 decoded tok/s and 8,000 / 2,500 prefill tok/s for small / 27B models.
- Batched: lockstep cohorts of ≥ 16 in flight, with aggregate decode speedup 5× / 8× / 12× (low / mid / high).
- Batch-invariant kernels at 0.4 / 0.6 / 0.8 of the non-invariant throughput.
- $2.49 per pod-hour; 8 quads per server start.

**Grading:**
- Sonnet-class grader at $2 / $10 per MTok list price, half price in batch.
- Rubric read from cache, on a 50% quad subsample, plus a 10% second-family subsample.
- **$0.0036 per game** in the study ($0.0096 if the rubric does not cache), against **$0.018** as filed.

Total cost for one replicate, all five models (`results/cost_model.json`):

| stories | S6 as filed (re-run with measured tokens) | new probes | + prefix caching | + batched (low / mid / high) | + batched, batch-invariant (low / mid / high) |
|---|---|---|---|---|---|
| 26 | $88 (28.0 GPU h) | $69 | $56 | $22 / $19 / $18 | $40 / $25 / $19 |
| 30 (Lean) | $102 (32.3 h) | $80 | $64 | $26 / $22 / $20 | $46 / $29 / $22 |
| 72 (Standard) | $244 (77.0 h) | $190 | $153 | $61 / $52 / $47 | $108 / $68 / $52 |

**Notes:**
- "Low / mid / high" are the assumption brackets, not uncertainty intervals. The mid column of the batched variants is
  the working estimate until S4 measures throughput.
- Under batching, **model loading becomes a large share**: 8 quads per start means 7–18 starts per model, at 3–8
  minutes each. Raising quads per start under batching cuts this further. Restart drift is handled by blocking, not by
  frequent restarts.
- S6 as filed gave $95 for 26 stories and $109 for 30, against $88 and $102 here. Measured tokens raised prefill and
  lowered decode; decode costs more per token, so the net is slightly lower.

## Part C: what the owner chooses before the pilot, and what the pilot then measures

1. **Serving mode.** `strict` needs no pipeline change. `throughput` or `throughput_invariant` needs pipeline v1.3.0
   (P12), an amendment of D1 and D9 for Missing Piece, and the S0-GPU checks C1–C3 (`gates/S0/S0_GPU_PLAN.md`).
2. **The S4 pilot runs in the mode chosen for the confirmatory run**, through `mp.runner.run_lockstep`. Every call
   records server-reported prompt, cached and completion tokens, latency and cohort. `cost_model.measured_costs()`
   turns these into per-game GPU-seconds by model size.
3. **S6 recompute (owner's item 5).** Before any tier or equivalence decision, the tier table is recomputed with:
   - the S4 variance components (80th percentile), which set MDE and TOST power;
   - the S4 measured per-call costs, which set GPU hours and dollars.

   The power columns of the provisional table do not change with the serving mode or the probe policy: the primary
   outcome and its estimator are untouched. Only the cost columns move.
