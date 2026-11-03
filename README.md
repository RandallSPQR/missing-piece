# Missing Piece (revision 2)

**Question.** When one agent advocates an objectively false report, does support among the other four agents depend
on whether the advocate privately knows it is false, and on whether one of them holds contradicting evidence?

**Status (2026-11-03).** Gates S0 (CPU), S1 and S2-lint pass. The analysis code is validated on synthetic data. The S6
power simulation exists in a **provisional, proxy-variance** form. S0-GPU, S2 model checks, S3, S4 and S5 are built and
wait for the owner's approval of GPU spend.
- **Not frozen.** No paid collection. Nothing confirmatory.
- Brief: https://claude.ai/artifact/8KE5pFnmDEdJYGyHTjDcG7 (revision 2).
- **Complementary to Stigmergic Phase Transitions (StPT)**, not the same experiment through two channels. The two share
  the scenario format, the evidence schema, the pinned pipeline and the coordination record.

## Pins (`pins.yaml`; copied into every run manifest by `mp.manifest.header`)

| what | where | tag | commit |
|---|---|---|---|
| Shared five-model pipeline (no serving is built here; D41: Missing Piece on v1.3.0, StPT on v1.2.0) | RandallSPQR/SAE-Ethos-Calibration | `v1.3.0` | `37031bcd0d33b6dbd2c6f6573127714367c306fe` |
| Shared coordination record | [RandallSPQR/StPT-MP-Coordination](https://github.com/RandallSPQR/StPT-MP-Coordination) | none | `d031729bb1a1` (MP entries through A35, P16, on branch `claude/festive-ritchie-e5hga4` over main `80e9992`) |
| Evidence schema | coordination `schema/evidence_schema_v1.0.json` | 1.0 | copy in `gates/S1/schema/` |

**What the coordination record holds:**
- the decision register (`DECISIONS.md`);
- the shared protocol specification and the evidence-schema version (`PROTOCOL_SPEC.md`, `schema/`);
- the pipeline identity (`PIPELINE.md`, `pipeline.yaml`);
- the development / confirmatory separation (`DATA_SEPARATION.md`);
- the amendment and deviation log (`AMENDMENTS.md`);
- the claim-provenance index (`PROVENANCE_INDEX.md`).

**Models:**
- Llama-3.1-8B-Instruct, Gemma-2-9B-IT, Gemma-3-27B-IT.
- Qwen3.5-9B and Qwen3.5-27B, thinking off (pencilled).

All five come from the pinned lineup: bf16, batch size 1, exact logprobs.

## Design

- **Groups.** Five single-family agents, labelled Agent 1–5. Positions are randomised and roles are never named. One
  agent is the speaker and four are receivers.
- **2 × 2.** Speaker knowledge (uninformed / knowing) × verifier (absent / present).
  - The same false report, word for word and framed as hearsay, appears in all four cells.
  - The advocacy objective is identical in every cell, with no instruction to persuade despite falsity.
  - The knowing speaker also holds a firsthand record that shows the report is false. The uninformed speaker holds a
    neutral record matched in format and length.
  - In verifier-present cells, one receiver holds the same record in place of a matched neutral one.
- **Protocol.**
  - R rounds (pilot; starting at 4) with a 60–120-word band (pilot). Speaking order is randomised per round.
  - Then a private vote: sampled at temperature 0.6, top-p 0.9, seeded. The exact P(A)/P(B) and non-A/B mass are
    recorded. An invalid vote gets 3 seeded retries and is then counted.
  - Then an exit poll.
  - Private conviction and comprehension probes run on forked branches and never return.
- **Controls.**
  - No communication.
  - Standardised complete-evidence disclosure (a diagnostic benchmark).
  - A solo pooled-evidence check (development bank).
  - Process measure: natural verifier disclosure.
- **Primary outcome.** The share of the four receivers whose final vote is the report option.
- **Confirmatory contrast (one).** The knowledge main effect, pooled over the five models as fixed strata,
  start-blocked, with stories as clusters. Secondary: knowledge × verifier and per-model effects. A separately powered
  TOST at ±0.05.

## Gates (in order; each blocks spend; stop and report after each)

| gate | status | report |
|---|---|---|
| S0 pipeline / serialisation | **CPU part passes**: pin checked; 5/5 templates hash to their pins; every multi-turn context agrees with the official template (55 per model; 56 for Llama, one extra vote retry). GPU part (token ids, option tokens, stop ids, repeat probe) pending | `gates/S0/S0_REPORT.md` |
| S1 evidence specifications | **passes** with conventions **proposed**: 12 development stories (32 specs incl. 8 challenge variants) and 26 confirmatory stories (52 specs); schema v1.0; all verifier-present cells solvable (2.79 ≥ 2.2) | `gates/S1/S1_REPORT.md`, `gates/S1/CONVENTIONS.md` |
| S2 scenario pipeline | **lint passes on both banks**; prior check and refusal screen built, pending GPU | `gates/S2/S2_REPORT.md` |
| S3 comprehension (dev, branched) + held-out | built (1,280 items per model per set), pending GPU | `gates/S3/S3_PLAN.md` |
| S4 pilot | **CPU probe isolation passes** (256 games, 7,682 live calls byte-identical; 256/256 leaky controls detected); pilot pending GPU | `gates/S4/S4_PLAN.md` |
| S5 grading reliability | rubric and blinded item builder drafted; pending pilot transcripts | `gates/S5/S5_PLAN.md` |
| S6 power and bounds | **provisional tier table on proxy variances**; re-run on S4 variance components before the owner picks | `gates/S6/S6_REPORT.md` |
| S7 freeze | not started | |

Analysis validation on synthetic data: **12/12 checks pass** (`analysis/VALIDATION_REPORT.md`).

**Cost reduction (owner, 2026-11-03; engineering only):**
- **Probes:** receivers only, at a midpoint round and the final round.
- **Batched lockstep runner:** the four cells of each quad share batches, and batch composition is recorded
  (`mp/runner.py`).
- **Serving modes:** `mp/serving.py` checks the mode. Prefix caching and batching need pipeline v1.3.0 (proposed,
  `proposals/pipeline-v1.3.0/`) and S0-GPU validation (`gates/S0/S0_GPU_PLAN.md`).
- **Pipeline (D41):** StPT stays on v1.2.0. Missing Piece is pinned to v1.3.0 (tagged `37031bcd`), with throughput
  modes opt-in, validated by S0-GPU first. The CPU link check passes: v1.3.0-strict serves exactly as v1.2.0
  (`gates/S0/link_check/`).
- **Probes:** P13 adds the speaker at the final round.
- **Grading:** Paper 1's graders via OpenRouter (Sonnet 4.5 primary, Gemini 2.5 Flash gate grader on the same items),
  a cached rubric, 100% speaker coding (P14) and a 50% quad subsample for the rest. Paper 1's kappa/AC1 gate is
  reproduced exactly (`mp/reliability.py`, `gates/S5/S5_PLAN.md`).
- **Costs:** recomputed from measured token counts (`gates/S6/COST_RECOMPUTE.md`). The final recompute uses the S4
  pilot's measured per-call costs, before any tier is chosen.
Draft pre-registration: `prereg/PREREGISTRATION_DRAFT.md`.

## Layout

```
mp/            study code: manifest (pins, server start), evidence model, prompts, game engine (protocol),
               assignment (paired quads, start blocking), backends (pinned serializer; mock; vLLM client),
               isolation check, screens, single-agent gate builders, grading items, analysis, simulator
gates/S0..S6/  gate scripts, results and reports
analysis/      synthetic validation
prereg/        draft pre-registration
tests/         pytest (CPU)
```

## Run (CPU)

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e .
python gates/S0/run_s0.py && python gates/S1/make_banks.py && python gates/S2/lint.py
python gates/S4/isolation_cpu.py && python analysis/validate_synthetic.py && python -m pytest -q tests
```
