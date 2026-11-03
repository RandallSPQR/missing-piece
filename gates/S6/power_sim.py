"""Gate S6 (PROVISIONAL, proxy variances): power simulation for the pooled knowledge effect, returned as a tier table.

What is real here: the estimator (mp.analysis.paired, the registered primary computation, run on every simulated
dataset), the design (stories as clusters, two truth-scenarios per story, four cells per quad within one server start,
five models as fixed strata), the worst-case cross-model correlation rho = 1 (carry-over 6), and the between-start
jitter (0.056 in vote probability, Gemma-3-27B's worst case, coordination A16).
What is NOT yet real: the variance components. Missing Piece has no development data (S3-S5 need GPU spend not yet
approved), so three proxy scenarios bracket them. Gate S6 proper re-runs this script with the S4 pilot's variance
components (80th percentile of their sampling distribution, as StPT D27 item 2) before the owner picks a tier.

Per configuration: N_SIM datasets at delta_K = 0 give the sampling SD of the estimate, the TOST power at the
proposed bound (+-0.05) and the interaction SD; the MDE at 80% power (two-sided alpha 0.05) is
(t_{0.975, K-1} + t_{0.80, K-1}) x SD; power at the reference effect 0.10 follows from the noncentral t, and is
checked by direct simulation at delta_K = 0.10 for the central scenario.
Costs: GPU from per-game token counts x throughput assumptions (stated below; replaced by S4 measured per-call costs);
grading from token counts x the grader's list price. Writes gates/S6/results/tier_table.json and .md."""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from mp import analysis as A  # noqa: E402
from mp.simulate import SimParams, simulate  # noqa: E402

N_SIM = int(sys.argv[1]) if len(sys.argv) > 1 else 300
REF_MAIN, REF_INT, BOUND = 0.10, 0.10, 0.05
STORIES = [12, 18, 24, 26, 30, 36, 48, 60, 72]
REPS = [1, 2]
SCENARIOS = {   # proxy variance components on the support scale (owner: these are assumptions, not measurements)
    "optimistic": dict(sd_game=0.20, sd_slope_story=0.05, sd_slope_scen=0.03, sd_slope_int_story=0.05),
    "central": dict(sd_game=0.25, sd_slope_story=0.08, sd_slope_scen=0.04, sd_slope_int_story=0.08),
    "pessimistic": dict(sd_game=0.35, sd_slope_story=0.12, sd_slope_scen=0.06, sd_slope_int_story=0.12),
}
COMMON = dict(n_models=5, rho=1.0, sd_jitter=0.056, sd_start=0.01, quads_per_start=8)

# ---- cost assumptions (to be replaced by S4 per-call measurements) ----
COST = {
    "gpu_usd_per_hour": 2.49,          # RTX PRO 6000 Blackwell; derived from StPT's approved S8 cap ($22.40 / 9 pod-hours, D27)
    "decode_tok_per_game": 3400,       # 4 rounds x 5 messages x ~150 tokens + exit polls + votes
    "prefill_tok_per_game": 90000,     # prefix caching off: every call re-reads its context (messages, votes, exit, probes)
    "requests_per_game": 70,
    "small": {"decode_tps": 90, "prefill_tps": 8000, "load_min": 3},     # 8-9B, bf16, batch 1
    "large": {"decode_tps": 30, "prefill_tps": 2500, "load_min": 8},     # 27B, bf16, batch 1
    "request_overhead_s": 0.05,
    "models": {"small": 3, "large": 2},   # Llama-8B, Gemma-2-9B, Qwen3.5-9B / Gemma-3-27B, Qwen3.5-27B
    "quads_per_start": 8,
    # grading (secondary measures only): Claude Opus 5.5 via the Message Batches API ($4 / $20 per MTok, batch 50% off)
    "grade_in_tok_per_game": 6000, "grade_out_tok_per_game": 600, "grade_usd_in_per_mtok": 4.0 * 0.5,
    "grade_usd_out_per_mtok": 20.0 * 0.5, "second_grader_share": 0.10,
}


def cost(K, n_rep):
    games_per_model = K * 2 * 4 * n_rep
    quads_per_model = K * 2 * n_rep
    gpu_h = 0.0
    for size, n_models in COST["models"].items():
        c = COST[size]
        s = (COST["decode_tok_per_game"] / c["decode_tps"] + COST["prefill_tok_per_game"] / c["prefill_tps"]
             + COST["requests_per_game"] * COST["request_overhead_s"])
        starts = math.ceil(quads_per_model / COST["quads_per_start"])
        gpu_h += n_models * (games_per_model * s / 3600 + starts * c["load_min"] / 60)
    games = games_per_model * 5
    g = games * (COST["grade_in_tok_per_game"] * COST["grade_usd_in_per_mtok"]
                 + COST["grade_out_tok_per_game"] * COST["grade_usd_out_per_mtok"]) / 1e6
    g *= 1 + COST["second_grader_share"]
    return {"games": games, "gpu_hours": round(gpu_h, 1), "gpu_usd": round(gpu_h * COST["gpu_usd_per_hour"], 0),
            "grading_usd": round(g, 0), "total_usd": round(gpu_h * COST["gpu_usd_per_hour"] + g, 0)}


def run(scen, K, n_rep, delta=0.0, n=N_SIM, seed0=0):
    est, ests_int, eq = [], [], []
    for s in range(n):
        recs = simulate(SimParams(n_stories=K, n_rep=n_rep, delta_K=delta, **COMMON, **SCENARIOS[scen]),
                        seed=seed0 + 7919 * s + K * 13 + n_rep)
        w = A.quads(A.frame(recs))
        r = A.paired(w, "d_K", bound=BOUND)
        est.append(r["estimate"]); eq.append(r["equivalent"])
        ests_int.append(A.paired(w, "d_KV")["estimate"])
    return np.array(est), np.array(ests_int), np.array(eq)


def power_t(effect, sd, df, alpha=0.05):
    nc = effect / sd
    q = stats.t.ppf(1 - alpha / 2, df)
    p = float(stats.nct.sf(q, df, nc) + stats.nct.cdf(-q, df, nc))
    if not math.isfinite(p):          # scipy's noncentral t fails for very large noncentrality: normal approximation
        p = float(stats.norm.sf(q - nc) + stats.norm.cdf(-q - nc))
    return p


def main():
    t0 = time.time()
    rows = []
    for scen in SCENARIOS:
        for K in STORIES:
            for n_rep in REPS:
                e, ei, eq = run(scen, K, n_rep)
                sd, sdi, df = float(e.std(ddof=1)), float(ei.std(ddof=1)), K - 1
                m = stats.t.ppf(0.975, df) + stats.t.ppf(0.80, df)
                row = {"scenario": scen, "stories": K, "scenarios": 2 * K, "replicates": n_rep,
                       "sd_estimate": round(sd, 4), "mde_main_80": round(m * sd, 3),
                       "power_main_at_0.10": round(power_t(REF_MAIN, sd, df), 3),
                       "tost_power_at_0_bound_0.05": round(float(eq.mean()), 3),
                       "mde_interaction_80": round(m * sdi, 3),
                       "power_interaction_at_0.10": round(power_t(REF_INT, sdi, df), 3),
                       "type1_check": None, **cost(K, n_rep)}
                rows.append(row)
                print(scen, K, n_rep, row["mde_main_80"], row["power_main_at_0.10"], row["tost_power_at_0_bound_0.05"],
                      row["total_usd"], f"{time.time() - t0:.0f}s", flush=True)
    # direct check of the analytic power at 0.10 (central scenario, three sizes)
    checks = []
    for K in (24, 36, 48):
        e, _, _ = run("central", K, 1, delta=REF_MAIN, n=N_SIM, seed0=99)
        # power by the real test needs p-values: recompute the t statistic from the estimates' SD under the null run
        sd0 = next(r["sd_estimate"] for r in rows if r["scenario"] == "central" and r["stories"] == K and r["replicates"] == 1)
        checks.append({"stories": K, "analytic": power_t(REF_MAIN, sd0, K - 1),
                       "simulated_share_est_above_crit": float(np.mean(e / sd0 > stats.t.ppf(0.975, K - 1)))})
    out = {"status": "PROVISIONAL: proxy variance components; S6 proper re-runs with S4 pilot variances",
           "n_sim": N_SIM, "reference_effects": {"main": REF_MAIN, "interaction": REF_INT}, "tost_bound": BOUND,
           "alpha": 0.05, "rho_cross_model": 1.0, "models": 5, "scenarios": SCENARIOS, "common": COMMON,
           "cost_assumptions": COST, "rows": rows, "power_checks": checks, "seconds": round(time.time() - t0)}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "tier_table.json").write_text(json.dumps(out, indent=1) + "\n")
    md = ["| scenario | stories (clusters) | scenarios | reps | games | GPU h | GPU $ | grading $ | total $ | MDE main (80%) | power at 0.10 | TOST power (+-0.05, true 0) | MDE interaction | power int. at 0.10 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['scenario']} | {r['stories']} | {r['scenarios']} | {r['replicates']} | {r['games']} | {r['gpu_hours']} | "
                  f"{r['gpu_usd']:.0f} | {r['grading_usd']:.0f} | {r['total_usd']:.0f} | {r['mde_main_80']:.3f} | "
                  f"{r['power_main_at_0.10']:.2f} | {r['tost_power_at_0_bound_0.05']:.2f} | {r['mde_interaction_80']:.3f} | "
                  f"{r['power_interaction_at_0.10']:.2f} |")
    (HERE / "results" / "tier_table.md").write_text("\n".join(md) + "\n")
    print("done", out["seconds"], "s; checks", checks)


if __name__ == "__main__":
    main()
