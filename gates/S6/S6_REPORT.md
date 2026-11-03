# S6 report: power simulation and proposed bounds (PROVISIONAL: proxy variances)

**Date:** 2026-11-03.
**Status:** **provisional.** Gate S6 proper needs the S4 pilot's variance components, and S4 has not run (GPU not
approved).

This report fixes the machinery and gives the owner a first tier table on **proxy** variance components:
- The design, estimator, correlation assumption and between-start jitter are real.
- The variance components are not.

When S4 has run, the same script re-runs on the S4 components, taken at the 80th percentile of their sampling
distribution with pilot point estimates sealed (as StPT D27), and the owner picks a tier from that table.

**Re-run:**

```bash
python gates/S6/power_sim.py 300
```

```bash
python gates/S6/tiers.py
```

Outputs: `results/tier_table.json`, `results/tier_table.md`, `results/tiers.json`, `results/tiers.md`.

## What is simulated

- **Estimand.** The pooled knowledge effect: uninformed minus knowing receiver support, averaged over verifier
  conditions, five models as fixed strata with equal weights. It is one confirmatory test (D2, D5).
- **Estimator.** Every simulated dataset goes through the registered primary computation, `mp.analysis.paired`. This is
  the same code as the confirmatory analysis.
  - It is start-blocked through within-quad contrasts.
  - Stories are the clusters, with the two truth-scenarios of a story averaged inside it.
  - Models are averaged inside the story before the between-story spread is taken.
- **Clusters, not replicates.** Power comes from independent stories. Replicates per scenario-cell shrink only the
  within-quad part of the variance.
- **Worst-case cross-model correlation: ρ = 1** (carry-over 6). A story's knowledge slope is shared exactly by all five
  models, so averaging over models does not shrink between-story variance.
- **Between-start jitter.** 0.056 in vote probability per game: Gemma-3-27B's worst case from StPT S4 (A16), applied to
  every model.
- **Systematic start offsets.** SD 0.01, against ≤ 0.0043 measured (generous).
- **Game-level probability.** Beta-distributed with the cell's exact mean, so there is no clipping bias. Votes are 4
  receivers, Binomial. The invalid-vote rate is 0.003.
- **Equivalence.** TOST at ±0.05 (α 0.05 per side), with the true effect 0, by direct simulation.
- **Reference effects.** 0.10 for the knowledge main effect and 0.10 for the interaction (proposed).
- **MDE.** At 80% power, two-sided α 0.05: (t₀.₉₇₅ + t₀.₈₀) × the simulated SD of the estimate.
- **Simulation size.** 300 datasets per configuration.

### Proxy variance scenarios (assumptions, not measurements)

| scenario | game-level SD of support (within cell) | between-story SD of the knowledge effect | between-scenario SD | between-story SD of the interaction |
|---|---|---|---|---|
| optimistic | 0.20 | 0.05 | 0.03 | 0.05 |
| central | 0.25 | 0.08 | 0.04 | 0.08 |
| pessimistic | 0.35 | 0.12 | 0.06 | 0.12 |

The game-level SD carries discussion dynamics: herding makes the four receivers' votes move together. With four
receivers, 0.35 is close to the maximum possible.

### Cost assumptions (to be replaced by S4 per-call measurements)

**GPU (one RTX PRO 6000 Blackwell, bf16, batch size 1, prefix cache off):**
- **Per game:** about 3,400 decoded tokens (4 rounds × 5 messages of about 150 tokens, plus votes and exit polls),
  about 90,000 prefill tokens (every call re-reads its context, conviction probes included) and about 70 requests.
- **Throughput:**
  - 8–9B models: 90 decoded tok/s and 8,000 prefill tok/s;
  - 27B models: 30 decoded tok/s and 2,500 prefill tok/s.
- **Model loads:** 3 minutes (small) and 8 minutes (large) per server start, with 8 quads per start.
- **Price:** $2.49 per pod-hour, derived from StPT's approved S8 cap ($22.40 for 9 pod-hours, D27). Treat it as an upper
  estimate.

**Grading (secondary measures only):**
- Claude Opus 5.5 through the Message Batches API ($4 / $20 per MTok list price, half price in batch).
- About 6,000 input and 600 output tokens per game, plus a 10% second-family subsample.

**Not in the table:**
- development work: S0-GPU, S2, S3 ≈ $3–5; the S4 pilot ≈ $14; S5 pilot grading ≈ $5;
- the control arms (no-communication and standardised disclosure have no discussion, so they cost about a tenth of a
  natural game per game).

## Result 1: proposed tiers (rules fixed in `tiers.py` before reading the table)

- **Lean:** the cheapest configuration that detects 0.10 at 80% even in the **pessimistic** proxy scenario.
- **Standard:** the cheapest configuration with TOST power ≥ 0.80 at ±0.05 in the **central** scenario.
- **Strong:** the same TOST requirement in the **pessimistic** scenario.

| tier | stories | scenarios | reps | games | GPU h | total $ (GPU + grading) | scenario | MDE main | power at 0.10 | TOST power | MDE interaction |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Lean | 30 | 60 | 1 | 1200 | 34.2 | 109 | optimistic | 0.059 | 1.00 | 0.63 | 0.099 |
| Lean | 30 | 60 | 1 | 1200 | 34.2 | 109 | central | 0.069 | 0.98 | 0.36 | 0.108 |
| Lean | 30 | 60 | 1 | 1200 | 34.2 | 109 | pessimistic | 0.093 | 0.85 | 0.04 | 0.137 |
| Standard | 72 | 144 | 1 | 2880 | 81.6 | 260 | optimistic | 0.034 | 1.00 | 0.99 | 0.069 |
| Standard | 72 | 144 | 1 | 2880 | 81.6 | 260 | central | 0.044 | 1.00 | 0.89 | 0.072 |
| Standard | 72 | 144 | 1 | 2880 | 81.6 | 260 | pessimistic | 0.057 | 1.00 | 0.56 | 0.094 |
| Strong | not reached in the grid (≤ 72 stories, ≤ 2 replicates) |||||||||||

Read with the cost assumptions above. Total $ = GPU + grading. Games = stories × 2 truths × 4 cells × replicates × 5
models.

## Result 2: the tier table (selected rows; every row is in `results/tier_table.md`)

Rows shown: 24, 26, 30, 36, 48, 60 and 72 stories; 1 or 2 replicates; three proxy scenarios. ρ = 1. 300 simulated
datasets per row.

| scenario | stories | scenarios | reps | games | GPU h | GPU $ | grading $ | total $ | MDE main (80%) | power at 0.10 | TOST power (±0.05, true 0) | MDE interaction | power int. at 0.10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| optimistic | 24 | 48 | 1 | 960 | 27.2 | 68 | 19 | 87 | 0.063 | 0.99 | 0.44 | 0.120 | 0.65 |
| optimistic | 24 | 48 | 2 | 1920 | 54.4 | 135 | 38 | 174 | 0.055 | 1.00 | 0.74 | 0.081 | 0.93 |
| optimistic | 26 | 52 | 1 | 1040 | 29.7 | 74 | 21 | 95 | 0.061 | 1.00 | 0.47 | 0.109 | 0.73 |
| optimistic | 26 | 52 | 2 | 2080 | 58.9 | 147 | 41 | 188 | 0.051 | 1.00 | 0.77 | 0.091 | 0.87 |
| optimistic | 30 | 60 | 1 | 1200 | 34.2 | 85 | 24 | 109 | 0.059 | 1.00 | 0.63 | 0.099 | 0.81 |
| optimistic | 30 | 60 | 2 | 2400 | 68.0 | 169 | 48 | 217 | 0.044 | 1.00 | 0.87 | 0.078 | 0.95 |
| optimistic | 36 | 72 | 1 | 1440 | 40.8 | 102 | 29 | 130 | 0.049 | 1.00 | 0.75 | 0.098 | 0.82 |
| optimistic | 36 | 72 | 2 | 2880 | 81.6 | 203 | 57 | 260 | 0.043 | 1.00 | 0.91 | 0.064 | 0.99 |
| optimistic | 48 | 96 | 1 | 1920 | 54.4 | 135 | 38 | 174 | 0.039 | 1.00 | 0.93 | 0.081 | 0.93 |
| optimistic | 48 | 96 | 2 | 3840 | 108.8 | 271 | 76 | 347 | 0.035 | 1.00 | 0.98 | 0.059 | 1.00 |
| optimistic | 60 | 120 | 1 | 2400 | 68.0 | 169 | 48 | 217 | 0.039 | 1.00 | 0.95 | 0.066 | 0.99 |
| optimistic | 60 | 120 | 2 | 4800 | 136.0 | 339 | 95 | 434 | 0.029 | 1.00 | 1.00 | 0.052 | 1.00 |
| optimistic | 72 | 144 | 1 | 2880 | 81.6 | 203 | 57 | 260 | 0.034 | 1.00 | 0.99 | 0.069 | 0.98 |
| optimistic | 72 | 144 | 2 | 5760 | 163.2 | 406 | 114 | 521 | 0.027 | 1.00 | 1.00 | 0.052 | 1.00 |
| central | 24 | 48 | 1 | 960 | 27.2 | 68 | 19 | 87 | 0.084 | 0.91 | 0.15 | 0.130 | 0.58 |
| central | 24 | 48 | 2 | 1920 | 54.4 | 135 | 38 | 174 | 0.066 | 0.99 | 0.38 | 0.093 | 0.85 |
| central | 26 | 52 | 1 | 1040 | 29.7 | 74 | 21 | 95 | 0.075 | 0.96 | 0.18 | 0.125 | 0.61 |
| central | 26 | 52 | 2 | 2080 | 58.9 | 147 | 41 | 188 | 0.060 | 1.00 | 0.46 | 0.096 | 0.83 |
| central | 30 | 60 | 1 | 1200 | 34.2 | 85 | 24 | 109 | 0.069 | 0.98 | 0.36 | 0.108 | 0.74 |
| central | 30 | 60 | 2 | 2400 | 68.0 | 169 | 48 | 217 | 0.053 | 1.00 | 0.59 | 0.090 | 0.88 |
| central | 36 | 72 | 1 | 1440 | 40.8 | 102 | 29 | 130 | 0.063 | 0.99 | 0.48 | 0.108 | 0.74 |
| central | 36 | 72 | 2 | 2880 | 81.6 | 203 | 57 | 260 | 0.058 | 1.00 | 0.66 | 0.072 | 0.97 |
| central | 48 | 96 | 1 | 1920 | 54.4 | 135 | 38 | 174 | 0.056 | 1.00 | 0.65 | 0.090 | 0.88 |
| central | 48 | 96 | 2 | 3840 | 108.8 | 271 | 76 | 347 | 0.043 | 1.00 | 0.87 | 0.066 | 0.99 |
| central | 60 | 120 | 1 | 2400 | 68.0 | 169 | 48 | 217 | 0.050 | 1.00 | 0.78 | 0.086 | 0.90 |
| central | 60 | 120 | 2 | 4800 | 136.0 | 339 | 95 | 434 | 0.040 | 1.00 | 0.94 | 0.059 | 1.00 |
| central | 72 | 144 | 1 | 2880 | 81.6 | 203 | 57 | 260 | 0.044 | 1.00 | 0.89 | 0.072 | 0.97 |
| central | 72 | 144 | 2 | 5760 | 163.2 | 406 | 114 | 521 | 0.036 | 1.00 | 0.96 | 0.054 | 1.00 |
| pessimistic | 24 | 48 | 1 | 960 | 27.2 | 68 | 19 | 87 | 0.102 | 0.79 | 0.01 | 0.154 | 0.45 |
| pessimistic | 24 | 48 | 2 | 1920 | 54.4 | 135 | 38 | 174 | 0.089 | 0.89 | 0.06 | 0.123 | 0.62 |
| pessimistic | 26 | 52 | 1 | 1040 | 29.7 | 74 | 21 | 95 | 0.106 | 0.75 | 0.01 | 0.148 | 0.47 |
| pessimistic | 26 | 52 | 2 | 2080 | 58.9 | 147 | 41 | 188 | 0.088 | 0.89 | 0.05 | 0.110 | 0.72 |
| pessimistic | 30 | 60 | 1 | 1200 | 34.2 | 85 | 24 | 109 | 0.093 | 0.85 | 0.04 | 0.137 | 0.53 |
| pessimistic | 30 | 60 | 2 | 2400 | 68.0 | 169 | 48 | 217 | 0.076 | 0.96 | 0.12 | 0.111 | 0.71 |
| pessimistic | 36 | 72 | 1 | 1440 | 40.8 | 102 | 29 | 130 | 0.082 | 0.93 | 0.08 | 0.128 | 0.59 |
| pessimistic | 36 | 72 | 2 | 2880 | 81.6 | 203 | 57 | 260 | 0.076 | 0.96 | 0.22 | 0.101 | 0.79 |
| pessimistic | 48 | 96 | 1 | 1920 | 54.4 | 135 | 38 | 174 | 0.074 | 0.97 | 0.25 | 0.108 | 0.74 |
| pessimistic | 48 | 96 | 2 | 3840 | 108.8 | 271 | 76 | 347 | 0.066 | 0.99 | 0.42 | 0.083 | 0.92 |
| pessimistic | 60 | 120 | 1 | 2400 | 68.0 | 169 | 48 | 217 | 0.061 | 1.00 | 0.37 | 0.092 | 0.86 |
| pessimistic | 60 | 120 | 2 | 4800 | 136.0 | 339 | 95 | 434 | 0.053 | 1.00 | 0.67 | 0.077 | 0.95 |
| pessimistic | 72 | 144 | 1 | 2880 | 81.6 | 203 | 57 | 260 | 0.057 | 1.00 | 0.56 | 0.094 | 0.85 |
| pessimistic | 72 | 144 | 2 | 5760 | 163.2 | 406 | 114 | 521 | 0.052 | 1.00 | 0.73 | 0.066 | 0.99 |

**Check.** Analytic power at 0.10 from the simulated SD (noncentral t) against direct simulation at δ = 0.10, central
scenario:
- 24 stories: 0.914 vs 0.923;
- 36 stories: 0.994 vs 0.990;
- 48 stories: 0.999 vs 1.000.

Source: `results/tier_table.json`, `power_checks`.

## Reading (all of it conditional on the proxy variances)

1. **Detecting the reference effect (0.10) is cheap.**
   - The current 26-story confirmatory bank, with one replicate, gives an MDE of 0.075 (central) or 0.106 (pessimistic),
     at about $95.
   - 30 stories bring the pessimistic MDE under 0.10 (0.093), at about $109.
2. **The equivalence claim is what costs.**
   - TOST at ±0.05 needs about 60–72 stories × 1 replicate in the central scenario (power 0.78–0.89, about $217–260).
   - In the pessimistic scenario it is not reached inside the grid: 0.73 at 72 stories × 2 replicates, about $521.
   - Under the brief's rule ("if no affordable tier reaches a meaningful effect, scope is cut rather than the sample
     inflated"), the owner chooses between three options:
     - (a) the Standard tier, with a bank expanded to about 72 stories;
     - (b) a wider equivalence bound;
     - (c) Lean, with a stated TOST power.
3. **More stories beat more replicates.** For the same money, adding stories shrinks the between-story slope variance,
   which dominates under ρ = 1. Replicates shrink only the within-quad noise. Example: 72 × 1 ($260) has more TOST
   power than 48 × 2 ($347) in every scenario.
4. **The interaction** (secondary, no power target) has an MDE of about 0.05–0.15 across these rows. In the central
   scenario, a 0.10 interaction is detectable at 80% from 24 stories × 2 replicates (0.85) or 48 stories × 1 (0.88).
   At 26 × 1 the power is 0.61.
5. **Bank size.** The confirmatory bank holds 26 stories.
   - Lean (30) or Standard (72) needs the bank expanded, as StPT did under D29. That means the same generator, writer
     rules, independent review, lint, prior check and refusal screen, all before any confirmatory call.
   - New stories are written blind to every outcome.

## Proposed for the owner (P10)

- **Smallest effect of interest:** 0.10 in receiver support for the knowledge main effect. It matches the D14
  reference effect, whose half (0.05) is Missing Piece's tripwire.
- **Smallest effect for the interaction:** 0.10. It is secondary, so no power target is set.
- **Equivalence bound:** ±0.05 (half the reference effect).
- **Tier:** to be picked from the S6 table re-run on S4 variance components. Provisionally, Lean (30 stories, 1
  replicate) if no equivalence claim is wanted, or Standard (72 stories, 1 replicate) if it is.
- **Budget cap:** still unresolved in the coordination record ("Both: budget cap … per-stage caps"); it is needed before
  the tier is picked.

**Stop here.** S6 proper re-runs this after S4.

