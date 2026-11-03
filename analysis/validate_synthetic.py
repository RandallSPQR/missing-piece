"""Analysis-code validation on synthetic data (brief: sign recovery, null behaviour, paired assignment, branch isolation;
plus a blinded permutation check through the real code, the registered mixed-model rule, TOST behaviour, and an
end-to-end engine -> analysis run). Every check has a pass rule stated here, before it runs. CPU only.

Writes analysis/results/validation.json."""
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from mp import analysis as A  # noqa: E402
from mp import isolation  # noqa: E402
from mp.assign import make_plan, schedule  # noqa: E402
from mp.backend import MockBackend  # noqa: E402
from mp.protocol import Settings, briefings, run_game  # noqa: E402
from mp.simulate import SimParams, simulate  # noqa: E402

N = 400                    # simulated datasets per condition
BASE = dict(n_stories=26, n_models=5, n_rep=1)
res = {"n_sims": N, "checks": {}}
t0 = time.time()


def sims(delta_K, delta_KV=0.0, n=N, **kw):
    out = []
    for s in range(n):
        recs = simulate(SimParams(**{**BASE, **kw}, delta_K=delta_K, delta_KV=delta_KV), seed=10_000 + s)
        w = A.quads(A.frame(recs))
        out.append((A.paired(w, "d_K", bound=0.05), A.paired(w, "d_KV")))
    return out


# 1 sign recovery: rule = mean estimate within 0.01 of truth; >= 95% of estimates have the true sign at delta = +-0.10
for d in (0.10, -0.10):
    r = sims(d)
    e = np.array([x[0]["estimate"] for x in r])
    cover = np.mean([x[0]["ci95"][0] <= d <= x[0]["ci95"][1] for x in r])
    res["checks"][f"sign_recovery_{d:+.2f}"] = {
        "mean_estimate": float(e.mean()), "sd": float(e.std()), "share_true_sign": float(np.mean(np.sign(e) == np.sign(d))),
        "ci95_coverage": float(cover), "power_two_sided": float(np.mean([x[0]["p_two_sided"] < 0.05 for x in r])),
        "pass": bool(abs(e.mean() - d) < 0.01 and np.mean(np.sign(e) == np.sign(d)) >= 0.95 and cover >= 0.92)}

# 2 null behaviour: rule = type-I rate in [0.03, 0.07] (N = 400: +-2.2 SE around 0.05), KS test of p-values p > 0.01
r0 = sims(0.0)
p = np.array([x[0]["p_two_sided"] for x in r0])
pint = np.array([x[1]["p_two_sided"] for x in r0])
res["checks"]["null_behaviour"] = {
    "type1_knowledge": float(np.mean(p < 0.05)), "type1_interaction": float(np.mean(pint < 0.05)),
    "ks_uniform_p": float(stats.kstest(p, "uniform").pvalue),
    "tost_declares_equivalence_at_0": float(np.mean([x[0]["equivalent"] for x in r0])),
    "pass": bool(0.03 <= np.mean(p < 0.05) <= 0.07 and 0.03 <= np.mean(pint < 0.05) <= 0.07
                 and stats.kstest(p, "uniform").pvalue > 0.01)}

# 2b null with worst-case cross-model correlation and heavy story slopes: rule = type-I in [0.03, 0.07]
r0b = sims(0.0, rho=1.0, sd_slope_story=0.15)
res["checks"]["null_rho1_heavy_slopes"] = {"type1": float(np.mean([x[0]["p_two_sided"] < 0.05 for x in r0b])),
                                           "pass": bool(0.03 <= np.mean([x[0]["p_two_sided"] < 0.05 for x in r0b]) <= 0.07)}

# 3 TOST: rule = at delta 0.10 the equivalence (+-0.05) is declared in < 5% of datasets (it is false there)
r1 = sims(0.10, n=200)
res["checks"]["tost_false_equivalence_at_0.10"] = {
    "rate": float(np.mean([x[0]["equivalent"] for x in r1])),
    "pass": bool(np.mean([x[0]["equivalent"] for x in r1]) < 0.05)}

# 3b TOST at the bound: rule = at delta = +0.05 (the bound), equivalence declared in <= 5% + MC error (alpha control)
rb = sims(0.05, n=400)
rate_b = float(np.mean([x[0]["equivalent"] for x in rb]))
res["checks"]["tost_alpha_at_bound"] = {"rate": rate_b, "pass": bool(rate_b <= 0.072)}

# 4 interaction recovery: rule = mean estimate within 0.015 of 0.10
ri = sims(0.0, delta_KV=0.10, n=200)
ei = np.array([x[1]["estimate"] for x in ri])
res["checks"]["interaction_recovery"] = {"mean_estimate": float(ei.mean()), "pass": bool(abs(ei.mean() - 0.10) < 0.015)}

# 5 paired assignment (engine): rule = the four cells of a quad share every random draw and differ only in the one
#   record line of the speaker and of the verifier holder; F's letter balanced within every server start (|A-B| <= 1);
#   analysis refuses an incomplete quad and a quad that spans starts.
spec = json.loads((ROOT / "gates/S1/banks/development/mp-dev-ferry-timetable-B.json").read_text())
plan = make_plan(spec, "gemma-2-9b-it", 0, rounds=4)
B = {c: briefings(spec, plan, c, "MP-W1") for c in ("UA", "UP", "KA", "KP")}
others_same = all(len({B[c][k] for c in B}) == 1 for k in range(1, 6) if k not in (plan.speaker, plan.verifier_holder))
recs_e = [run_game(spec, plan, c, MockBackend("gemma-2-9b-it"), Settings()) for c in ("UA", "UP", "KA", "KP")]
same_plan = len({json.dumps([r["speaker"], r["verifier_holder"], r["letter_of"], r["orders"]]) for r in recs_e}) == 1
specs = [json.loads(p.read_text()) for p in sorted((ROOT / "gates/S1/banks/development").glob("*.json"))]
sch = schedule(specs, "qwen3.5-9b", n_rep=2, quads_per_start=8, rounds=4)
bal = {}
for s in sch:
    F = s["spec"]["evidence_model"]["report_option"]
    bal.setdefault(s["start_block"], []).append(s["plan"].letter_of[F])
letter_ok = all(abs(v.count("A") - v.count("B")) <= 1 for v in bal.values())
recs = simulate(SimParams(n_stories=4, n_models=2), seed=3)
bad_inc = recs[1:]
bad_span = [dict(r, start_id="X") if i == 0 else r for i, r in enumerate(recs)]
refused = []
for bad in (bad_inc, bad_span):
    try:
        A.quads(A.frame(bad))
        refused.append(False)
    except ValueError:
        refused.append(True)
res["checks"]["paired_assignment"] = {"non_holder_briefings_identical_across_cells": others_same,
                                      "cells_share_plan": same_plan, "F_letter_balanced_within_starts": letter_ok,
                                      "starts_checked": len(bal), "refuses_incomplete_quad": refused[0],
                                      "refuses_quad_spanning_starts": refused[1],
                                      "pass": bool(others_same and same_plan and letter_ok and all(refused))}

# 6 branch isolation: rule = byte-identical live calls with and without probes; leaky negative control detected
iso = [isolation.check(spec, make_plan(spec, m, 0, 4, tag="val"), c, lambda m=m: MockBackend(m))
       for m in ("llama-3.1-8b-it", "gemma-3-27b-it") for c in ("UA", "KP")]
res["checks"]["branch_isolation"] = {"games": len(iso), "identical": sum(r["identical_with_probes"] for r in iso),
                                     "controls_detected": sum(r["negative_control_detected"] for r in iso),
                                     "pass": all(r["identical_with_probes"] and r["negative_control_detected"] for r in iso)}

# 7 blinded permutation check through the real code: rule = story-level permutation null centred on 0 (|mean| < 0.003)
#   and the permutation p-value within 0.03 of the story-clustered t-test p-value (same null: no mean effect across
#   stories). The quad-level (sharp-null) permutation is reported as a diagnostic; it answers a different question
#   (inference conditional on the bank) and is expected to give a smaller p when story slopes vary.
recs = simulate(SimParams(**BASE, delta_K=0.04), seed=77)
w = A.quads(A.frame(recs))
obs = A.paired(w)
null = A.permutation_null(w, n=4000, seed=1, level="story")
nullq = A.permutation_null(w, n=2000, seed=2, level="quad")
p_perm = float(np.mean(np.abs(null) >= abs(obs["estimate"])))
res["checks"]["blinded_permutation"] = {"null_mean": float(null.mean()), "null_sd": float(null.std()),
                                        "observed": obs["estimate"], "p_t": obs["p_two_sided"], "p_perm_story": p_perm,
                                        "p_perm_quad_diagnostic": float(np.mean(np.abs(nullq) >= abs(obs["estimate"]))),
                                        "pass": bool(abs(null.mean()) < 0.003 and abs(p_perm - obs["p_two_sided"]) < 0.03)}

# 8 registered mixed model vs paired estimator: rule = the route taken is recorded and its estimate is within 0.01 of
#   the paired estimate on 5 datasets
mm = []
for s in range(5):
    recs = simulate(SimParams(**BASE, delta_K=0.10), seed=500 + s)
    r = A.registered_primary(A.frame(recs))
    pe = A.paired(A.quads(A.frame(recs)))["estimate"]
    mm.append({"route": r["route"], "estimate": r["estimate"], "paired": pe})
res["checks"]["mixed_vs_paired"] = {"rows": mm, "pass": all(abs(x["estimate"] - x["paired"]) < 0.01 for x in mm)}

# 9 engine -> analysis end to end (mock backend; mechanics only): rule = analyse() runs on engine records
eng = []
for sp in specs[:8]:
    for m in ("gemma-2-9b-it", "qwen3.5-9b"):
        pl = make_plan(sp, m, 0, rounds=2)
        pl.start_id = f"{m}/mockstart0"
        for c in ("UA", "UP", "KA", "KP"):
            eng.append(run_game(sp, pl, c, MockBackend(m), Settings(rounds=2), probes=True))
out = A.analyse(eng)
res["checks"]["engine_to_analysis"] = {"games": len(eng), "quads": out["n_quads"], "stories": out["n_stories"],
                                       "pass": out["n_quads"] == len(eng) // 4}

res["all_pass"] = all(v["pass"] for v in res["checks"].values())
res["seconds"] = round(time.time() - t0, 1)
(HERE / "results").mkdir(exist_ok=True)
(HERE / "results" / "validation.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
for k, v in res["checks"].items():
    print(k, "PASS" if v["pass"] else "FAIL", {kk: vv for kk, vv in v.items() if kk not in ("rows", "pass")})
print("ALL PASS:", res["all_pass"], res["seconds"], "s")
