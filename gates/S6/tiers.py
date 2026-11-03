"""Reads results/tier_table.json and proposes three tiers by rules fixed here (before reading the table):
  Lean      cheapest configuration whose MDE for the knowledge effect is <= 0.10 in the PESSIMISTIC proxy scenario
  Standard  cheapest configuration with TOST power >= 0.80 at the +-0.05 bound (true effect 0) in the CENTRAL scenario
  Strong    cheapest configuration with TOST power >= 0.80 in the PESSIMISTIC scenario
Each tier is shown under all three proxy scenarios. Also re-computes any power value the noncentral t returned as NaN
(normal approximation). Writes results/tiers.json and results/tiers.md."""
import json
import math
from pathlib import Path

from scipy import stats

HERE = Path(__file__).resolve().parent
T = json.loads((HERE / "results/tier_table.json").read_text())
rows = T["rows"]


def pw(effect, sd, df):
    nc, q = effect / sd, stats.t.ppf(0.975, df)
    p = float(stats.nct.sf(q, df, nc) + stats.nct.cdf(-q, df, nc))
    return p if math.isfinite(p) else float(stats.norm.sf(q - nc) + stats.norm.cdf(-q - nc))


for r in rows:
    df = r["stories"] - 1
    r["power_main_at_0.10"] = round(pw(0.10, r["sd_estimate"], df), 3)
    sdi = r["mde_interaction_80"] / (stats.t.ppf(0.975, df) + stats.t.ppf(0.80, df))
    r["power_interaction_at_0.10"] = round(pw(0.10, sdi, df), 3)
key = lambda r: (r["total_usd"], r["stories"])  # noqa: E731


def pick(scen, ok):
    c = sorted([r for r in rows if r["scenario"] == scen and ok(r)], key=key)
    return (c[0]["stories"], c[0]["replicates"]) if c else None


tiers = {"Lean": pick("pessimistic", lambda r: r["mde_main_80"] <= 0.10),
         "Standard": pick("central", lambda r: r["tost_power_at_0_bound_0.05"] >= 0.80),
         "Strong": pick("pessimistic", lambda r: r["tost_power_at_0_bound_0.05"] >= 0.80)}
out, md = {}, ["| tier | stories | scenarios | reps | games | GPU h | total $ (GPU + grading) | scenario | MDE main | power at 0.10 | TOST power | MDE interaction |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for name, cfg in tiers.items():
    if cfg is None:
        out[name] = None
        md.append(f"| {name} | not reached in the grid (≤ 72 stories, ≤ 2 replicates) |||||||||||")
        continue
    sel = [r for r in rows if (r["stories"], r["replicates"]) == cfg]
    out[name] = sel
    for r in sorted(sel, key=lambda r: ["optimistic", "central", "pessimistic"].index(r["scenario"])):
        md.append(f"| {name} | {r['stories']} | {r['scenarios']} | {r['replicates']} | {r['games']} | {r['gpu_hours']} | "
                  f"{r['total_usd']:.0f} | {r['scenario']} | {r['mde_main_80']:.3f} | {r['power_main_at_0.10']:.2f} | "
                  f"{r['tost_power_at_0_bound_0.05']:.2f} | {r['mde_interaction_80']:.3f} |")
(HERE / "results/tiers.json").write_text(json.dumps({"rules": __doc__, "tiers": tiers, "rows": out}, indent=1) + "\n")
(HERE / "results/tiers.md").write_text("\n".join(md) + "\n")
T["rows"] = rows
(HERE / "results/tier_table.json").write_text(json.dumps(T, indent=1) + "\n")
print("\n".join(md))
full = ["| scenario | stories | scenarios | reps | games | GPU h | GPU $ | grading $ | total $ | MDE main (80%) | power at 0.10 | TOST power (±0.05, true 0) | MDE interaction | power int. at 0.10 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    full.append(f"| {r['scenario']} | {r['stories']} | {r['scenarios']} | {r['replicates']} | {r['games']} | {r['gpu_hours']} | "
                f"{r['gpu_usd']:.0f} | {r['grading_usd']:.0f} | {r['total_usd']:.0f} | {r['mde_main_80']:.3f} | "
                f"{r['power_main_at_0.10']:.2f} | {r['tost_power_at_0_bound_0.05']:.2f} | {r['mde_interaction_80']:.3f} | "
                f"{r['power_interaction_at_0.10']:.2f} |")
(HERE / "results/tier_table.md").write_text("\n".join(full) + "\n")
