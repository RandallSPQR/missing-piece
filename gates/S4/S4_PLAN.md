# S4 plan: pilot on the development bank

**Status:** the CPU probe-isolation check **passes** (`results/isolation_cpu.json`). The pilot itself is **not run**
(GPU, awaiting approval).

Revised 2026-11-03 for the owner's cost-reduction items (engineering only, no design change):
- probes for receivers only, at a midpoint round and the final round;
- batched lockstep serving with batch composition recorded;
- measured per-call costs, used to recompute S6 before any tier choice.

## CPU probe isolation: PASS

`python gates/S4/isolation_cpu.py`:

- **Sequential:**
  - Scope: every development scenario (32) × all four cells × two serializers (gemma2, qwen3_5) = 256 games;
    7,682 live calls compared.
  - Every game's live calls (serialised prompt sha256 and output, in order) are byte-identical with and without the
    conviction probes. That is 2,304 probes under the new policy: 4 receivers × rounds 2 and 4, plus the speaker at round 4.
  - A leaky probe (one that writes its trace into the event list) was detected in every game.
- **Lockstep (batched runner):** 128 games run in cohorts with and without probes are identical, and the leaky control
  is detected.

The engine rebuilds each live context from the game's event list. Probes run on fresh copies and write only to a probe
log that no live context reads. On GPU, byte-identity of live **outputs** under batching needs batch-invariant kernels
(`gates/S0/S0_GPU_PLAN.md`).

## Probe policy (owner, 2026-11-03; P13 approved)

- **Private conviction probes:**
  - the four receivers, after round ⌈R/2⌉ (round 2 when R = 4) and after round R;
  - **plus the speaker after round R** (P13), for the advocate's private conviction named in the mechanism hypothesis.

  That is 9 readouts per game, against 20 under the earlier schedule. `Settings(probe_labels="receivers",
  probe_rounds="midpoint_final", probe_speaker_final=True)`; the earlier schedule is `probe_labels="all",
  probe_rounds="every"`.
- **More probes only if the pilot shows they are needed.** Rule, fixed now: if the receivers' mean conviction changes
  by more than 0.05 between rounds 2 and 4 in any cell (pooled over models), a round-3 receiver probe is added before
  S6.

## Serving

- **Batched runner.** `mp.runner.run_lockstep` advances all games of a server start call by call. The k-th calls of the
  four cells of every quad are submitted in the same cohort. Every call records its cohort; every cohort records its
  members (game, call kind, agent) and wall time.
- **Mode (D41).** Missing Piece moves to pipeline v1.3.0 once it is applied and tagged. Its S0-GPU check validates the
  throughput modes before any other run. The pilot then runs in the mode chosen for the confirmatory run: `strict`, or
  a validated `throughput` / `throughput_invariant`.

  The same mode serves all four cells, and it is recorded in the manifest (`mp.manifest.header(..., serving_mode=)`).
  `mp.serving.check_mode` refuses a mode the installed pipeline does not support or that has not passed S0-GPU for the
  model.

## Pilot (GPU)

Development bank only. All four cells of each quad run within one server start, and F's display letter is balanced
within each start.

| question | design | pre-stated rule |
|---|---|---|
| Rounds R | 4 (brief's start); receivers' conviction recorded after rounds 2 and 4 | R = 4 stands if the receivers' mean conviction changes by < 0.02 between rounds 2 and 4, pooled over models (95% CI inside ±0.04); otherwise R goes to the owner. Never chosen on a knowledge contrast |
| Message band | 60–120 words; out-of-band messages counted, never regenerated | stands if ≥ 90% of messages are inside it for every model; otherwise the instruction or band is revised and logged before S6 |
| Probe isolation (GPU) | strict, or `throughput_invariant`: byte-identity on 2 quads per model in one start. `throughput`: C3-style distributional equivalence, probes on vs off | as stated; the weaker `throughput` check needs the owner's acceptance |
| Disclosure mechanics | standardised complete-evidence disclosure arm | runs end to end; list comprehension ≥ 0.90 (one branched check per agent) |
| No-communication control | each agent votes on its own briefing | runs end to end |
| Invalid votes | strict one-letter instruction; 3 seeded retries | invalid rate reported by cell; non-A/B mass recorded |
| Variance components for S6 | between-story, between-scenario and within-quad variance of the knowledge contrast, per model | **knowledge and interaction point estimates sealed** (written once, hash in the coordination record's `SEALED.md`, opened only at the owner's request), as StPT D27 |
| **Measured per-call costs** | server-reported prompt, cached and completion tokens and latency per call; cohort wall time | feed `gates/S6/cost_model.measured_costs()`; S6 is recomputed with them **before** any tier or equivalence decision |

## Pilot size and cost

- **Size:** 6 development stories × 2 truths × 1 replicate × 4 cells = 48 games per model, 240 games in total.
- **Cost, from `gates/S6/results/cost_model.json`:**
  - `strict`: about 0.7 pod-hours for each of the three small models and about 1.9 for each 27B model; about 6
    pod-hours in total with loads, about $15.
  - `throughput` (assumed mid speedup): about 1.5 pod-hours, about $4.
  - The S0-GPU C3 games in the candidate mode can count toward the pilot.

## Sampling settings (proposed; not in the brief)

- **Discussion messages:** temperature 0.7, top-p 0.95, seeded per call; max 320 tokens.
- **Votes:** temperature 0.6, top-p 0.9 (brief), seeded; max 4 tokens.
- **Exit polls:** as messages, max 120 tokens.
- Seeds are shared across the four cells of a quad (common random numbers).
