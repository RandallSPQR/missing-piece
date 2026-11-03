# S0, GPU part: plan (not run; awaits the owner's approval of GPU spend)

Everything here runs on the D12 GPU type (RTX PRO 6000 Blackwell) on approved pods. Every run manifest carries the pins,
the identity block, the server-start ID and the serving mode.

## Part 1: v1.2.0 (strict) checks, as already planned

- **Token-level agreement:** `apply_to_tokenizer` ids against the template's ids.
- **Option tokens:** `A` and `B` are single tokens after each generation prompt.
- **Stop ids.**
- **Repeat probe:** a repeat probe on a multi-turn Missing Piece vote prompt within one start.

Cost: under one pod-hour.

## Part 2: serving-mode validation (owner, 2026-11-03: prefix caching, batched serving)

### Why this needs a new pipeline version

Pipeline v1.2.0 fixes `--no-enable-prefix-caching` and `--max-num-seqs 1` in its locked `lineup.yaml`
(`serving.determinism.flags`). `lineup-serve-cmd` and the identity block are built from that list. Missing Piece cannot
turn caching or batching on without changing a pinned serving value.

**Proposed:** pipeline **v1.3.0**, not v1.2.1, which is the rejected restart-drift candidate (A6).
- **Patch:** `proposals/pipeline-v1.3.0/`, against `5ca15f56`. CPU tests: 43 pass and 24 skipped, the same skips as
  v1.2.0.
- **Additive.** The default mode `strict` is the v1.2.0 flag set unchanged, so StPT is unaffected.
- **Opt-in modes:**
  - `throughput`: prefix caching on, 32 sequences in flight, per-request cache-hit reporting.
  - `throughput_invariant`: as `throughput`, plus vLLM batch-invariant kernels.
- The identity block records the mode.

Logged in the coordination record as a proposed pipeline change (P12). Using it also amends D1 (batch size 1) and D9
(prefix cache off) for Missing Piece, which needs the owner's decision.

### Checks

Each check runs per model, in each candidate mode. Rules: `gates/S0/serving_check.py`, fixed before any call.

| check | what | pass |
|---|---|---|
| C1 caching, readouts, **within one start** | 64 vote prompts read with a cold cache (after `POST /reset_prefix_cache`; server started with `VLLM_SERVER_DEV_MODE=1`, which exposes that endpoint and changes no numerics) and again warm | max \|Δ\| ≤ 0.25 nats on log P(A), log P(B) and logit_AB; ≤ 5% of prompts with \|Δ logit_AB\| > 0.05 |
| C2 batching, readouts, within one start | the same prompts read alone and inside a cohort of 32 concurrent requests | `throughput`: as C1. `throughput_invariant`: every Δ exactly 0 |
| C3 games, distributions | 8 development quads (32 games) per model in `strict` (sequential) and in the mode (lockstep), same plans and seeds, so games are paired | pooled over the 5 models: the 95% bootstrap CI of the paired receiver-support difference includes 0 and lies inside ±0.10; message words KS p > 0.01; out-of-band rate Δ < 0.05; non-A/B mass Δ < 0.01; no increase in invalid votes. Per-model differences reported; any model whose own CI excludes 0 goes to the owner |

**Why C1 and C2 run within one start.** Switching caching on or off needs a server restart, and restarts alone move
logits by up to 0.25 nats (StPT S0; S4 puts it at ≤ 0.056 in vote probability). Within one start, cold vs warm and alone
vs batched isolate the effect of caching and batching.

**Batch invariance on this GPU is unknown.** vLLM 0.19.1 documents `VLLM_BATCH_INVARIANT` for compute capability
≥ 9.0, tested on H100/H200/B100/B200.
- The RTX PRO 6000 is sm_120. In vLLM's code it takes the generic fallback, not the B-series path.
- The mode needs the FLASH_ATTN or TRITON_ATTN backend.
- The Qwen3.5 hybrid layers (Gated DeltaNet) are not on vLLM's tested list.

C2 under `throughput_invariant` settles it per model. If it fails, `throughput` (non-invariant) is the fallback.

**What non-invariant batching means for the design.**
- Outputs become reproducible only in distribution: a call's numerics can depend on what else is in flight.
- The four cells of a quad are interleaved in the same cohorts (`mp.runner.run_lockstep`), so any such effect is
  balanced across cells. Batch composition is recorded for every call.
- The probe-isolation check changes meaning on GPU:
  - **Structural isolation is unaffected.** Probe answers never enter a live context; this is verified on CPU, and in
    lockstep the live calls are identical with and without probes.
  - **Byte-identity of live outputs on GPU holds only under batch invariance, or in strict mode.** Probe requests share
    batches with live calls, so without invariance they can perturb live outputs numerically. They carry no
    information, but the perturbation is real.
  - Under `throughput`, the GPU isolation check is replaced by C3-style distributional equivalence (probes on vs off).
    That is a weaker check than the brief's "byte-identical" requirement, and it is the owner's call to accept it.

### Cost

- C1 and C2: about 0.2 pod-hours.
- C3: about 5 pod-hours (the strict arm dominates), about $12.
- If C1–C3 pass, the C3 games in the candidate mode count toward the S4 pilot.
