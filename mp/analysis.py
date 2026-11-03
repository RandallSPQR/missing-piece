"""Missing Piece analysis (draft; frozen at S7 with its hash posted before any confirmatory game).

Unit: the game (one cell of one quad). Outcome: receiver support = share of the FOUR receivers whose final private vote is
the report option (an invalid vote is not a report vote; no exclusion on any post-treatment measure; a tipping-point
analysis counts invalid votes as report votes instead).

Every quad runs its four cells within ONE server start, so every within-quad contrast is blocked by start (D14, D22).

CONFIRMATORY (one test, D5): the knowledge main effect, uninformed minus knowing, averaged over verifier conditions,
pooled across the models as FIXED strata with equal weights (D2), generalising to new stories:
    d_q   = mean(UA, UP) - mean(KA, KP)                        per quad (start-blocked by construction)
    D_sm  = mean of d_q over scenario s's replicates for model m
    D_k   = mean over the scenarios (truth A, truth B) of story k and over the M models (equal weights)
    Delta = mean_k D_k ;  SE = sd_k(D_k) / sqrt(K) ;  t with K - 1 df ; two-sided alpha 0.05
Stories are the independent clusters (the two truth-scenarios of a story share text). Averaging over models INSIDE the
story before taking the between-story spread makes the test valid under any cross-model correlation, including the
worst case rho = 1 (carry-over 6).
EQUIVALENCE: TOST at +-0.05 (two one-sided t tests at alpha 0.05; equivalently the 90% CI inside the bound).
REGISTERED MODEL (brief): mixed model support ~ K x V + C(start) with story random intercepts and knowledge slopes
(scenario-within-story variance component where identifiable). Rule fixed now: the mixed model is reported if it
converges with a non-singular random-effect covariance; otherwise the slope is dropped; if it still fails, the paired
estimator above is the registered fallback. With every quad complete within a start the two target the same estimand.
CONDITIONAL ON THE BANK (reported separately, labelled): stories fixed; uncertainty from replicate variation only.
SECONDARY: knowledge x verifier interaction (two-sided), per-model knowledge effects, verifier main effect, all with
intervals and no multiplicity correction claims.
"""
from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd
from scipy import stats

CELLS = ("UA", "UP", "KA", "KP")


def frame(records: list[dict]) -> pd.DataFrame:
    cols = ["quad_id", "scenario_id", "story_id", "model", "replicate", "start_id", "cell", "knowing", "verifier",
            "receiver_support", "receiver_invalid", "challenge_set"]
    df = pd.DataFrame([{k: r.get(k) for k in cols} for r in records])
    return df


def quads(df: pd.DataFrame, invalid_as_report: bool = False) -> pd.DataFrame:
    """One row per quad with the four cell outcomes. Refuses quads that are incomplete or span server starts."""
    y = df["receiver_support"] + (df["receiver_invalid"] / 4.0 if invalid_as_report else 0.0)
    w = df.assign(y=y).pivot_table(index=["quad_id", "scenario_id", "story_id", "model", "replicate"], columns="cell",
                                   values="y", aggfunc="first")
    starts = df.groupby("quad_id")["start_id"].nunique()
    if (starts > 1).any():
        raise ValueError(f"quads span server starts: {list(starts[starts > 1].index)[:5]}")
    missing = w[list(CELLS)].isna().any(axis=1)
    if missing.any():
        raise ValueError(f"{int(missing.sum())} incomplete quads")
    w = w.reset_index()
    w["start_id"] = w["quad_id"].map(df.groupby("quad_id")["start_id"].first())
    w["d_K"] = (w.UA + w.UP) / 2 - (w.KA + w.KP) / 2          # uninformed minus knowing
    w["d_KV"] = (w.UP - w.KP) - (w.UA - w.KA)                  # knowledge effect, present minus absent
    w["d_K_absent"] = w.UA - w.KA
    w["d_K_present"] = w.UP - w.KP
    w["d_V"] = (w.UP + w.KP) / 2 - (w.UA + w.KA) / 2          # verifier present minus absent
    return w


def _cluster_test(D: np.ndarray, bound: float | None = None, alpha: float = 0.05) -> dict:
    K = len(D)
    est = float(D.mean())
    se = float(D.std(ddof=1) / math.sqrt(K)) if K > 1 else float("nan")
    df = K - 1
    t = est / se if se > 0 else float("nan")
    p = float(2 * stats.t.sf(abs(t), df)) if se > 0 else float("nan")
    q = stats.t.ppf(1 - alpha / 2, df)
    out = {"estimate": est, "se": se, "df": df, "t": t, "p_two_sided": p, "ci95": [est - q * se, est + q * se],
           "n_clusters": K}
    if bound is not None:
        q90 = stats.t.ppf(1 - alpha, df)
        p_lo = float(stats.t.sf((est + bound) / se, df))      # H0: effect <= -bound
        p_hi = float(stats.t.cdf((est - bound) / se, df))     # H0: effect >= +bound
        out.update({"tost_bound": bound, "tost_p": max(p_lo, p_hi), "ci90": [est - q90 * se, est + q90 * se],
                    "equivalent": max(p_lo, p_hi) < alpha})
    return out


def paired(w: pd.DataFrame, col: str = "d_K", models: list[str] | None = None, bound: float | None = None) -> dict:
    """Story-clustered, model-equal-weighted paired estimator (the registered primary computation)."""
    if models is not None:
        w = w[w.model.isin(models)]
    sm = w.groupby(["story_id", "scenario_id", "model"])[col].mean().reset_index()
    per_story_model = sm.groupby(["story_id", "model"])[col].mean().unstack("model")
    if per_story_model.isna().any().any():
        warnings.warn("some story x model cells are missing: equal model weights use the available models")
    D = per_story_model.mean(axis=1).to_numpy()
    out = _cluster_test(D, bound)
    out["models"] = sorted(w.model.unique())
    out["contrast"] = col
    return out


def conditional_on_bank(w: pd.DataFrame, col: str = "d_K") -> dict:
    """Stories and scenarios fixed: Var(Delta-hat) from replicate variation within (scenario, model) only."""
    g = w.groupby(["scenario_id", "model"])[col]
    n = g.size()
    if (n < 2).any():
        return {"estimate": float(w.groupby(["story_id", "scenario_id", "model"])[col].mean().mean()), "se": None,
                "note": "needs >= 2 replicates per scenario x model"}
    means, var = g.mean(), g.var(ddof=1)
    M = w.model.nunique()
    S = w.scenario_id.nunique()
    est = float(means.mean())
    se = float(math.sqrt((var / n).sum()) / (M * S))
    return {"estimate": est, "se": se, "ci95": [est - 1.96 * se, est + 1.96 * se], "inference": "conditional on bank"}


def mixed(df: pd.DataFrame, slope: bool = True) -> dict:
    """Registered mixed model: support ~ Kc * Vc + C(start) | story (intercept [+ knowledge slope])."""
    import statsmodels.formula.api as smf
    d = df.copy()
    d["Kc"] = np.where(d.knowing == 0, 0.5, -0.5)            # + = uninformed
    d["Vc"] = np.where(d.verifier == 1, 0.5, -0.5)
    d["y"] = d.receiver_support
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            m = smf.mixedlm("y ~ Kc * Vc + C(start_id)", d, groups=d["story_id"],
                            re_formula="~Kc" if slope else "~1",
                            vc_formula={"scenario": "0 + C(scenario_id)"}).fit(reml=True, method="lbfgs")
            ok = bool(m.converged)
            cov = np.asarray(m.cov_re)
            singular = bool(np.linalg.matrix_rank(cov) < cov.shape[0]) or bool(np.any(np.diag(cov) < 1e-10))
        except Exception as e:  # noqa: BLE001
            return {"converged": False, "error": str(e)[:200], "slope": slope}
    return {"converged": ok, "singular": singular, "slope": slope, "estimate": float(m.params["Kc"]),
            "se": float(m.bse["Kc"]), "p": float(m.pvalues["Kc"]),
            "interaction": float(m.params["Kc:Vc"]), "interaction_se": float(m.bse["Kc:Vc"])}


def registered_primary(df: pd.DataFrame) -> dict:
    """Apply the fixed rule: mixed with slope -> mixed without slope -> paired fallback."""
    for slope in (True, False):
        r = mixed(df, slope)
        if r.get("converged") and not r.get("singular"):
            r["route"] = "mixed_slope" if slope else "mixed_intercept"
            return r
    r = paired(quads(df))
    r["route"] = "paired_fallback"
    return r


def analyse(records: list[dict], bound: float = 0.05) -> dict:
    df = frame(records)
    w = quads(df)
    out = {
        "n_games": len(df), "n_quads": len(w), "n_stories": int(w.story_id.nunique()), "models": sorted(w.model.unique()),
        "confirmatory_knowledge_paired": paired(w, "d_K", bound=bound),
        "conditional_on_bank": conditional_on_bank(w, "d_K"),
        "secondary": {
            "interaction_KxV": paired(w, "d_KV"),
            "knowledge_verifier_absent": paired(w, "d_K_absent"),
            "knowledge_verifier_present": paired(w, "d_K_present"),
            "verifier_main": paired(w, "d_V"),
            "knowledge_by_model": {m: paired(w, "d_K", models=[m]) for m in sorted(w.model.unique())},
        },
        "tipping_point_invalid_as_report": paired(quads(df, invalid_as_report=True), "d_K"),
        "invalid_by_cell": df.groupby("cell")["receiver_invalid"].sum().to_dict(),
    }
    return out


def permutation_null(w: pd.DataFrame, n: int = 2000, seed: int = 0, level: str = "story") -> np.ndarray:
    """Blinded permutation check through the real estimator. The knowledge labels are swapped (UA<->KA and UP<->KP
    together, which flips the sign of d_K) for whole STORIES with probability 1/2 (level="story": the randomisation
    counterpart of the story-clustered generalisation test), or quad by quad (level="quad": the sharp null of no effect
    in any quad, the counterpart of inference conditional on the bank). The paired estimator is then recomputed."""
    rng = np.random.default_rng(seed)
    keys = w["story_id"] if level == "story" else w["quad_id"]
    uniq = keys.unique()
    out = np.empty(n)
    for i in range(n):
        flip = dict(zip(uniq, rng.choice([-1.0, 1.0], size=len(uniq))))
        out[i] = paired(w.assign(d_perm=w.d_K * keys.map(flip)), "d_perm")["estimate"]
    return out
