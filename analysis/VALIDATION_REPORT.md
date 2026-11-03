# Analysis-code validation on synthetic data

**Date:** 2026-11-03.
**Script:** `python analysis/validate_synthetic.py`. Results are in `results/validation.json`. CPU only; about 2 minutes.
**Result:** **all 12 checks pass.** Each check's pass rule is written in the script, above the check, before it runs.

**Data.** Synthetic datasets come from `mp/simulate.py`. They use the engine's record schema and have known effects:
- 26 stories × 2 truths × 5 models;
- story and scenario random intercepts and knowledge slopes, with cross-model correlation ρ = 1 unless stated;
- server-start offsets;
- between-start jitter of 0.056;
- Beta-distributed game probabilities, which keep the cell means exact;
- four receiver votes per game;
- an invalid-vote rate of 0.003.

The estimator under test is the registered primary computation, `mp.analysis.paired`: a story-clustered,
model-equal-weighted paired contrast that is start-blocked by construction.

| check | rule | result |
|---|---|---|
| sign recovery, δ = +0.10 (400 datasets) | mean estimate within 0.01 of truth; ≥ 95% with the true sign; 95% CI coverage ≥ 0.92 | mean 0.099; true sign 100%; coverage 0.94; power 0.96 |
| sign recovery, δ = −0.10 | same | mean −0.098; true sign 100%; coverage 0.94 |
| null behaviour (400) | type-I rate in [0.03, 0.07] for the main effect and for K × V; p-values uniform (KS p > 0.01) | main 0.045; interaction 0.053; KS p 0.39 |
| null, ρ = 1, heavy story slopes (SD 0.15) | type-I rate in [0.03, 0.07] | 0.055 |
| TOST: false equivalence at δ = 0.10 | < 5% | 0.0% |
| TOST: α at the bound (δ = +0.05) | ≤ 0.072 (5% + MC error) | 0.053 |
| interaction recovery, δ_KV = 0.10 | mean within 0.015 | 0.099 |
| paired assignment (engine) | cells of a quad share every random draw; non-holder briefings identical across cells; F's letter balanced within every start; analysis refuses incomplete quads and quads that span starts | all true |
| branch isolation (engine) | byte-identical live calls with and without probes; leaky negative control detected | 4/4 and 4/4 (and 256/256 in S4 CPU) |
| blinded permutation through the real code | story-level permutation null centred on 0 (\|mean\| < 0.003); permutation p within 0.03 of the t-test p | null mean −0.0009; p_perm 0.310 vs p_t 0.305 |
| registered mixed model vs paired estimator | the rule's route is recorded; estimate within 0.01 of the paired estimate | routes taken: slope ×3, intercept ×1, paired fallback ×1; all equal to the paired estimate |
| engine → analysis end to end (mock backend) | `analyse()` runs on engine records | 64 games, 16 quads |

## A failure, kept on record

The first run of the permutation check **failed** under its first rule: permutation p 0.202 against the t-test's 0.305.
- **Cause.** The first permutation flipped knowledge labels quad by quad. That tests the sharp null of no effect in any
  quad, which is the counterpart of inference conditional on the bank. The story-clustered t-test instead tests the
  null of no mean effect across stories, which is the generalisation target.
- **Change.** The check now permutes whole stories (the matching randomisation test). The rule was restated before the
  re-run, and the check passes.
- **Diagnostic kept.** The quad-level permutation is still reported. Its smaller p (0.218) is what the two inference
  targets should show when story slopes vary: the conditional-on-bank and generalisation results differ, and they are
  reported separately and labelled.

## Not yet validated (needs real data)

- Mixed-model convergence behaviour on real support distributions. The route rule is fixed in advance either way.
- Grading-based secondary measures (S5).
