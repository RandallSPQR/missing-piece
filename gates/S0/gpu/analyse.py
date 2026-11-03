"""Analyse Missing Piece S0-GPU results (rules fixed in gates/S0/S0_GPU_PLAN.md and gates/S0/serving_check.py).

Downloads every model's latest run from the artifacts dataset (missing-piece/S0/<run>/<model>/), then:
  Part 1   per model: token-level agreement, option tokens, stop ids, 8-repeat bit-identity, exact-fallback consistency
  C1, C2   per model and mode, as recorded on the pod
  C3       POOLED over the five models per mode (the rule), plus each model's own interval (reported; a model whose own
           95% CI excludes 0 goes to the owner)
  link     v1.3.0-strict readouts on StPT's three S0 prompts against StPT's recorded v1.2.0 S0 readouts (two starts):
           |difference| compared with the v1.2.0 restart difference (informative; different pods and dates)
  cost     measured wall time per game: strict sequential vs lockstep cohorts of 32 (feeds the S6 recompute)
Writes gates/S0/gpu/results/s0_gpu_results.json and s0_gpu_results.md. Raw files stay in the dataset (paths and sha256
in the results file)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gates/S0"))
from serving_check import game_compare  # noqa: E402

REPO = "RandallSPQR/stpt-gate-artifacts"
MODELS = ["llama-3.1-8b-it", "gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]
MODES = ["throughput", "throughput_invariant"]
CACHE = Path("/tmp/claude-0/-home-user/c33b92ab-3163-5d4d-bb33-9391ff19d3c0/scratchpad/s0gpu")


def fetch():
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi()
    fs = [f for f in api.list_repo_files(REPO, repo_type="dataset") if f.startswith("missing-piece/S0/")]
    latest = {}
    for f in fs:
        parts = f.split("/")
        if len(parts) >= 5 and parts[3] in MODELS:
            latest[parts[3]] = max(latest.get(parts[3], ""), parts[2])
    got = {}
    for f in fs:
        parts = f.split("/")
        if len(parts) >= 5 and parts[3] in MODELS and parts[2] == latest[parts[3]] and f.endswith((".json", ".txt", "DONE")):
            p = hf_hub_download(REPO, f, repo_type="dataset", local_dir=CACHE)
            got[f] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return latest, got


def ld(model, run, name):
    p = CACHE / "missing-piece/S0" / run / model / name
    return json.loads(p.read_text()) if p.exists() else None


def stpt_v120(model):
    """StPT S0's v1.2.0 readouts on the same three prompts (two server starts), from the same dataset."""
    from huggingface_hub import HfApi, hf_hub_download
    fs = [f for f in HfApi().list_repo_files(REPO, repo_type="dataset")
          if f.startswith("stpt/S0/box_identity/") and f.endswith((f"readout_{model}_1.json", f"readout_{model}_2.json"))]
    runs = {}
    for f in fs:
        runs.setdefault(f.split("/")[3], []).append(f)
    out = []
    for run in sorted(runs):
        for f in sorted(runs[run]):
            out.append(json.loads(Path(hf_hub_download(REPO, f, repo_type="dataset", local_dir=CACHE)).read_text()))
    return out


def main():
    latest, got = fetch()
    res = {"runs": latest, "files_sha256": got, "models": {}, "c3_pooled": {}}
    pooled = {m: ([], []) for m in MODES}
    md = ["| model | token agreement | options single | stop ids | repeats bit-identical | fallback | link: max |Δ| vs v1.2.0 (v1.2.0 restart Δ) |",
          "|---|---|---|---|---|---|---|"]
    for model in MODELS:
        run = latest.get(model)
        if not run:
            res["models"][model] = {"missing": True}
            md.append(f"| {model} | no results |||||"); continue
        p1, strict = ld(model, run, f"part1_{model}.json"), ld(model, run, f"c3_strict_{model}.json")
        wh = ld(model, run, "weight_hash.json")
        r = {"run": run, "weight_hash": wh, "part1_pass": p1 and p1.get("pass")}
        link = None
        if p1 and p1.get("link_check_readouts"):
            v12 = stpt_v120(model)
            if v12:
                cur = p1["link_check_readouts"]
                d = [abs(cur[k]["logp"][o] - x[k]["readout"]["logp"][o]) for x in v12 for k in cur for o in cur[k]["logp"]]
                rr = [abs(v12[i][k]["readout"]["logp"][o] - v12[j][k]["readout"]["logp"][o])
                      for i in range(len(v12)) for j in range(i + 1, len(v12)) for k in cur for o in cur[k]["logp"]]
                link = {"min_over_v120_starts_max_abs_nats": float(min(
                            max(abs(cur[k]["logp"][o] - x[k]["readout"]["logp"][o]) for k in cur for o in cur[k]["logp"])
                            for x in v12)),
                        "v120_restart_max_abs_nats": float(max(rr)) if rr else None, "n_v120_starts": len(v12),
                        "bit_identical_to_a_v120_start": any(all(cur[k]["logp"] == x[k]["readout"]["logp"] for k in cur) for x in v12)}
        r["link_check"] = link
        for mode in MODES:
            c12, c3 = ld(model, run, f"c12_{mode}_{model}.json"), ld(model, run, f"c3_{mode}_{model}.json")
            srv = ld(model, run, f"server_{mode}.json")
            r[mode] = {"server_up": srv and srv.get("up") == 1, "C1": c12 and c12["C1"], "C2": c12 and c12["C2"],
                       "C3_model": game_compare(strict["records"], c3["records"]) if strict and c3 else None,
                       "wall_s_per_game": (c3["wall_s"] / len(c3["records"])) if c3 else None}
            if strict and c3:
                pooled[mode][0].extend(strict["records"]); pooled[mode][1].extend(c3["records"])
        r["strict_wall_s_per_game"] = (strict["wall_s"] / len(strict["records"])) if strict else None
        res["models"][model] = r
        ta = p1 and p1.get("token_agreement") or {}
        live = (p1 or {}).get("live") or {}
        md.append(f"| {model} | {ta.get('agree')}/{ta.get('checked')} | {bool(p1 and p1.get('option_token_ids'))} | "
                  f"{bool(p1 and p1.get('check_tokenizer'))} | {all(v['repeat_probe']['bit_identical'] for v in live.values()) if live else None} | "
                  f"{all(v['fallback_consistency']['ok'] for v in live.values()) if live else None} | "
                  + (f"{link['min_over_v120_starts_max_abs_nats']:.4f} ({link['v120_restart_max_abs_nats']:.4f})" if link else "n/a") + " |")
    for mode in MODES:
        s, m = pooled[mode]
        res["c3_pooled"][mode] = game_compare(s, m) if s else None
    md += ["", "| mode | model | server up | C1 cache (max nats; pass) | C2 batching (max nats; pass) | C3 own Δ [95% CI] | s/game strict → mode |",
           "|---|---|---|---|---|---|---|"]
    for mode in MODES:
        for model in MODELS:
            r = res["models"].get(model, {}).get(mode)
            if not r:
                continue
            c1, c2, c3 = r["C1"], r["C2"], r["C3_model"]
            md.append(f"| {mode} | {model} | {r['server_up']} | " + (f"{c1['max_abs_nats']:.3f}; {c1['pass']}" if c1 else "–") + " | "
                      + (f"{c2['max_abs_nats']:.3f}; {c2['pass']}" if c2 else "–") + " | "
                      + (f"{c3['support_diff_mean']:+.3f} [{c3['support_diff_ci95'][0]:+.3f}, {c3['support_diff_ci95'][1]:+.3f}]" if c3 else "–") + " | "
                      + (f"{res['models'][model]['strict_wall_s_per_game']:.1f} → {r['wall_s_per_game']:.1f}" if r['wall_s_per_game'] and res['models'][model]['strict_wall_s_per_game'] else "–") + " |")
        p = res["c3_pooled"][mode]
        if p:
            md.append(f"| **{mode}** | **pooled ({p['quads']} quads)** | | | | **{p['support_diff_mean']:+.3f} [{p['support_diff_ci95'][0]:+.3f}, "
                      f"{p['support_diff_ci95'][1]:+.3f}]; KS p {p['words_ks_p']:.2f}; pass {p['pass']}** | |")
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/s0_gpu_results.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (HERE / "results/s0_gpu_results.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
