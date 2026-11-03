"""Grader agreement gate, adopted from Paper 1 (owner, 2026-11-03).

Source (verified wording and code): RandallSPQR/edsl_wwil @ 35ffd5dc68cab2b15f58c66b0b2a8a0c42159890,
two_truths_lie_study/PREREG_DRAFT.md section 6 "Agreement gate (per cue; frozen at the interim)", and the reference
implementation two_truths_lie_study/two_truths_lie/results/perfect_lie/prefreeze_checks/analysis/prefreeze_agreement.py
(kappa, ac1, boot). The functions below reproduce that code exactly (tests/test_reliability.py checks it against the
source file).

Paper 1's rule, verbatim:
  "A scorable cue is excluded from the primary score only if both Cohen's kappa and Gwet's AC1 have 95% lower bounds
   below 0.70. Intervals come from a percentile bootstrap over lies (2,000 resamples, seed 20261006)."
  "Minimum positives: 30. Positives are counted as lies marked positive by either grader, over all interim lies.
   A cue with fewer than 30 positives is not gated. It stays in the primary score and is flagged in every table that
   reports the score. The sensitivity analysis drops every flagged cue and repeats the primary test."
  "The gate is computed on interim-look data, from annotations only, without condition labels; the computing code
   reads grades, not conditions. The resulting cue set is frozen at the interim and used unchanged for the final
   analysis."
  Pairs: "Primary versus Google on every lie gates the cue set."

Missing Piece mapping: a "cue" is one binary graded code (each compliance category one-vs-rest, concession, verifier
disclosure, each exit-poll reason category); the unit ("lie") is a graded message or exit poll; the gate pair is the
primary grader vs the gate grader on every graded item. A code that fails the gate is dropped from the SECONDARY
analyses that use it (the primary outcome is ungraded). This module reads codes only, never cells or models."""
from __future__ import annotations

import numpy as np

THRESHOLD, MIN_POS, N_BOOT, SEED = 0.70, 30, 2000, 20261006


def kappa(a, b):
    po = np.mean(a == b); pa, pb = a.mean(), b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def ac1(a, b):
    po = np.mean(a == b); pi = (a.mean() + b.mean()) / 2
    pe = 2 * pi * (1 - pi)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def boot(a, b, f, n=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed); idx = np.arange(len(a)); v = []
    for _ in range(n):
        s = rng.choice(idx, len(idx)); x, y = a[s], b[s]
        if x.min() == x.max() and y.min() == y.max() and x[0] == y[0]:
            v.append(1.0); continue
        v.append(f(x, y))
    return np.percentile(v, [2.5, 97.5])


def gate(primary: dict, gate_grader: dict, codes: list[str]) -> dict:
    """primary, gate_grader: item id -> {code: bool}. Returns per code: positives, kappa and AC1 with 95% CIs,
    gated (>= 30 positives), excluded (gated and BOTH lower bounds < 0.70), flagged (< 30 positives: kept, flagged,
    dropped in the sensitivity analysis)."""
    ids = sorted(set(primary) & set(gate_grader))
    out = {}
    for c in codes:
        a = np.array([bool(primary[i][c]) for i in ids]); b = np.array([bool(gate_grader[i][c]) for i in ids])
        k, g = kappa(a, b), ac1(a, b)
        kl, ku = boot(a, b, kappa); gl, gu = boot(a, b, ac1)
        pos = int((a | b).sum())
        gated = pos >= MIN_POS
        out[c] = {"n_items": len(ids), "positives": pos, "kappa": float(k), "kappa_ci95": [float(kl), float(ku)],
                  "ac1": float(g), "ac1_ci95": [float(gl), float(gu)], "gated": gated,
                  "excluded": bool(gated and kl < THRESHOLD and gl < THRESHOLD), "flagged": not gated}
    return out
