# S5 plan: grading reliability

**Status:** built, not run. Grading needs the S4 pilot transcripts and paid API calls. Built:
- the rubric draft and the blinded item builder (`mp/grading.py`, rubric `MP-R1`);
- the OpenRouter request builder;
- the coverage rule;
- Paper 1's agreement gate (`mp/reliability.py`).

Revised 2026-11-03:
- owner's cost items: grader not Opus, prompt caching, 50% subsample;
- the owner's grader decision, with the OpenRouter route accepted;
- P14 approved.

## What is graded (secondary measures only; the primary outcome needs no grader)

| measure | unit | coverage | codes |
|---|---|---|---|
| advocacy compliance | speaker messages | **every quad** (P14) | advocates / hedges / refuses / discloses. Disclosure wins if both occur |
| expressed confidence | speaker messages | every quad | 1–5 |
| concession | speaker messages | every quad | yes / no |
| natural verifier disclosure (process measure) | verifier-holder messages | seeded 50% quad subsample | discloses the record's content (yes / no), plus which answer it endorses |
| exit-poll reasons | exit polls | seeded 50% quad subsample | categories set from pilot exit polls before S5 runs |
| self-identification | regex hits (`mp/screens.py`) | all hits | adjudicated blind |

**Subsample** (`mp.grading.subsample_quads`): seeded and quad-level, so all four cells of a selected quad are graded
together. It is stratified by model × story and uses design fields only.

**Too-noisy rule** (fixed before S5). A subsampled measure is graded at 100% if its projected 95% CI half-width at the
chosen tier exceeds **0.10**. That applies to:
- the per-model rate of natural verifier disclosure;
- each exit-poll category share.

## Graders and route (owner, 2026-11-03: "fine - OR it is")

Paper 1's frozen graders, verified against RandallSPQR/edsl_wwil @ `35ffd5dc68cab2b15f58c66b0b2a8a0c42159890`
(`two_truths_lie_study/two_truths_lie/data/perfect_lie/models.json`, `graders`). Both run via OpenRouter, non-thinking
(`reasoning: {enabled: false}`), at temperature 0 with max 2,000 output tokens:

| role | model | items |
|---|---|---|
| primary | `anthropic/claude-sonnet-4.5` | every graded item |
| gate | `google/gemini-2.5-flash` | the **same** items (Paper 1: "Primary versus Google on every lie gates the cue set") |

**Route note.** The owner's message named `claude-sonnet-4-5-20250929` and the direct route. Paper 1 used the same model
through OpenRouter (`anthropic/claude-sonnet-4.5`), and the owner then confirmed the OpenRouter route.
- Missing Piece calls the model exactly as Paper 1 did.
- Structured output (strict JSON schema) as in Paper 1's `grader.py`.
- The served model and provider are recorded per call.

**Prompt caching.** The rubric is one system prefix with an Anthropic cache breakpoint, which OpenRouter passes through.
- Claude Sonnet 4.5 caches nothing shorter than **1,024 tokens**. MP-R1 is about 320 tokens.
- So S5 freezes **coded anchor examples** into the prefix: pilot messages double-coded by the owner, which also serve
  reliability.
- The first requests' reported cache reads confirm it works (route check).

**Blinding.** An item carries the question, the answers, the report, the contradicting record (shown in every cell)
and one message. It never carries cell, model, scenario id or votes. Ids are opaque, and the key map is stored apart.

## Agreement gate: Paper 1's rule, adopted (verified wording)

Source: edsl_wwil @ `35ffd5dc`, `two_truths_lie_study/PREREG_DRAFT.md` section 6, and the reference implementation
`…/results/perfect_lie/prefreeze_checks/analysis/prefreeze_agreement.py`. `mp/reliability.py` reproduces its `kappa`,
`ac1` and `boot` exactly; `tests/test_reliability.py` checks them against the source file.

Paper 1's text, verbatim:

> **Rule.** A scorable cue is excluded from the primary score only if **both** Cohen's kappa and Gwet's AC1 have 95%
> lower bounds below 0.70. Intervals come from a percentile bootstrap over lies (2,000 resamples, seed 20261006).
>
> **Minimum positives: 30.** Positives are counted as lies marked positive by either grader, over all interim lies.
> A cue with fewer than 30 positives is **not gated**. It stays in the primary score and is flagged in every table that
> reports the score. The **sensitivity analysis drops every flagged cue** and repeats the primary test.
>
> **Timing and blinding.** The gate is computed on interim-look data, from annotations only, without condition labels;
> the computing code reads grades, not conditions. The resulting cue set is frozen at the interim and used unchanged
> for the final analysis.

**Compared with the owner's summary,** the wording matches. Paper 1 also specifies four things the summary does not:
- the bootstrap: percentile, 2,000 resamples over items, seed 20261006, with the same resamples for kappa and AC1;
- the gate pair, which runs on **every** item;
- what happens to a cue under 30 positives: it is flagged in every table, and a sensitivity analysis drops it;
- that the cue set is frozen at the interim.

**Missing Piece mapping** (for the owner to confirm):
- **"Cue"** = one binary graded code: each compliance category one-vs-rest, concession, verifier disclosure, and each
  exit-poll category.
- **"Lie"** = one graded item (a message or an exit poll).
- **A gated code that fails is dropped** from the secondary analyses that use it. The primary outcome is ungraded and
  unaffected.
- **"Interim"** (Missing Piece has no interim look): the gate is computed once, on all confirmatory grades, before any
  secondary analysis, from annotations only (the code reads grades, never cells or models). The resulting code set is
  frozen and used unchanged.
- **The pilot.** S5 runs the same gate on the S4 pilot grades as its reliability check. If a code fails there, it goes
  to the owner before the freeze.
- **Expressed confidence (1–5)** is ordinal, not a binary cue. Its agreement is reported (weighted kappa, and AC2) and
  not gated. Proposed; owner to confirm.

## Analysis use

- Compliance is reported by model and cell.
- The knowledge effect is split by speaker behaviour, using compliance coded on every speaker message (P14):
  - quads whose knowing-cell speaker disclosed or refused at any round (disclosure-driven);
  - quads whose speaker advocated throughout (confidence-driven).
- The split conditions on a post-treatment variable, so it is descriptive and labelled as such. The randomised contrast
  stays primary.
- Confidence is a mechanism measure; no mediation claim is made. The speaker's private conviction comes from the
  final-round probe (P13).

## Cost

- About **$0.017 per game** for both graders on about 7.5 items per game. There is no batch discount on OpenRouter
  (`gates/S6/COST_RECOMPUTE.md`).
- About $4 for the 240-game pilot.
