"""S0-GPU serving validation (owner, 2026-11-03): does prefix caching and/or batched serving change what the models do?
Runs on an approved pod only; the CPU self-test (`--self-test`) exercises every code path with the mock backend.

Three checks per model, rules fixed here before any GPU call:

  C1 caching, readout level, WITHIN one start (no restart drift). Server in a caching mode, started with
     VLLM_SERVER_DEV_MODE=1 (exposes POST /reset_prefix_cache; changes no numerics). For K = 64 vote prompts taken from
     development games: reset the cache, read out (cold), read out again (warm: prefix hit). Statistic: |delta| of
     log P(A), log P(B) and logit_AB, warm minus cold.
     PASS: max |delta| <= 0.25 nats (StPT S4's between-start maximum) and the share of prompts whose sampled vote
     could differ (|delta logit_AB| > 0.05) <= 5%.
  C2 batching, readout level, within one start. The same K prompts read alone (one in flight) and inside a cohort of
     32 concurrent requests. Same statistic. PASS (throughput): as C1. PASS (throughput_invariant): every delta == 0.
  C3 games, distribution level. N = 8 development quads (32 games) per model, run in `strict` (sequential, its own
     start) and in the candidate mode (lockstep, its own start), with the same plans and seeds, so games are paired.
     The rule below is applied POOLED over the five models (40 quads); per-model differences are reported, and any
     model whose own 95% CI excludes 0 is brought to the owner. If all checks pass, the candidate-mode games are
     development data in the protocol and may count toward the S4 pilot (same bank, same protocol).
     PASS, all of:
       - mean paired difference in receiver support (mode - strict) has a 95% CI (bootstrap over quads, 2,000
         draws) that includes 0 and lies inside +-0.10;
       - message word counts: two-sample KS p > 0.01; out-of-band rate differs by < 0.05;
       - non-A/B mass at the vote: mean differs by < 0.01; invalid votes: no increase beyond 1 per 64 games.
     (The two runs are in different starts, so restart drift is included; StPT S4 puts it at <= 0.056 in vote
     probability, well inside +-0.10.)
A mode is entered in pins.yaml `serving.validated_modes` for a model only if C1-C3 all pass for that model."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mp.assign import make_plan  # noqa: E402
from mp.protocol import Game, Settings  # noqa: E402
from mp.runner import run_lockstep  # noqa: E402

MAX_NATS, FLIP_NATS, FLIP_SHARE = 0.25, 0.05, 0.05


def readout_deltas(a: list[dict], b: list[dict]) -> dict:
    d = []
    for x, y in zip(a, b):
        la, lb = x["logp"] if "logp" in x else {k: np.log(v) for k, v in x["p"].items()}, \
            y["logp"] if "logp" in y else {k: np.log(v) for k, v in y["p"].items()}
        d.append({"A": abs(la["A"] - lb["A"]), "B": abs(la["B"] - lb["B"]),
                  "logit": abs((la["A"] - la["B"]) - (lb["A"] - lb["B"]))})
    mx = max(max(v.values()) for v in d) if d else 0.0
    flip = float(np.mean([v["logit"] > FLIP_NATS for v in d])) if d else 0.0
    return {"n": len(d), "max_abs_nats": float(mx), "share_logit_delta_gt_0.05": flip,
            "all_zero": all(max(v.values()) == 0 for v in d)}


def game_compare(strict_recs: list[dict], mode_recs: list[dict], seed: int = 0) -> dict:
    key = lambda r: r["game_id"]  # noqa: E731
    S, M = {key(r): r for r in strict_recs}, {key(r): r for r in mode_recs}
    common = sorted(set(S) & set(M))
    quads = sorted({g.rsplit("/", 1)[0] for g in common})
    dq = np.array([np.mean([M[g]["receiver_support"] - S[g]["receiver_support"] for g in common if g.startswith(q + "/")])
                   for q in quads])
    rng = np.random.default_rng(seed)
    boots = [rng.choice(dq, len(dq)).mean() for _ in range(2000)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    w = lambda R: [m["words"] for r in R for m in r["messages"]]  # noqa: E731
    oob = lambda R: np.mean([not m["in_band"] for r in R for m in r["messages"]])  # noqa: E731
    nab = lambda R: np.mean([v["readout"]["non_option_mass"] for r in R for v in r["votes"].values()])  # noqa: E731
    inv = lambda R: sum(r["receiver_invalid"] for r in R)  # noqa: E731
    Sx, Mx = [S[g] for g in common], [M[g] for g in common]
    ks = stats.ks_2samp(w(Sx), w(Mx)).pvalue
    out = {"games": len(common), "quads": len(quads), "support_diff_mean": float(dq.mean()), "support_diff_ci95": [float(lo), float(hi)],
           "words_ks_p": float(ks), "out_of_band_diff": float(oob(Mx) - oob(Sx)), "non_ab_mass_diff": float(nab(Mx) - nab(Sx)),
           "invalid_strict": int(inv(Sx)), "invalid_mode": int(inv(Mx))}
    out["pass"] = bool(lo <= 0 <= hi and -0.10 <= lo and hi <= 0.10 and ks > 0.01 and abs(out["out_of_band_diff"]) < 0.05
                       and abs(out["non_ab_mass_diff"]) < 0.01 and out["invalid_mode"] - out["invalid_strict"] <= max(1, len(common) // 64))
    return out


def dev_games(model, n_quads, backend, settings, tag="S0-serving"):
    specs = [json.loads(p.read_text()) for p in sorted((ROOT / "gates/S1/banks/development").glob("*.json"))
             if "challenge" not in p.name]
    random.Random(f"{tag}|{model}").shuffle(specs)
    return [Game(sp, make_plan(sp, model, 0, settings.rounds, tag=tag), c, backend, settings)
            for sp in specs[:n_quads] for c in ("UA", "UP", "KA", "KP")]


def self_test():
    """CPU: run C3's machinery on mock games (identical by construction) and C1/C2's on mock readouts."""
    from mp.backend import MockBackend
    be = MockBackend("gemma-2-9b-it")
    s = Settings()
    strict = [g.run(probes=True) for g in dev_games("gemma-2-9b-it", 8, be, s)]
    mode = run_lockstep(dev_games("gemma-2-9b-it", 8, be, s), be, probes=True)["records"]
    c3 = game_compare(strict, mode)
    msgs = [g.context(1, 0, "x") for g in dev_games("gemma-2-9b-it", 8, be, s)]
    ro = [be.readout(m) for m in msgs]
    c1 = readout_deltas(ro, [be.readout(m) for m in msgs])
    res = {"C1_mock": c1, "C3_mock": c3, "pass": bool(c1["all_zero"] and c3["games"] == 32 and c3["support_diff_mean"] == 0)}
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        out = self_test()
        (ROOT / "gates/S0/artifacts").mkdir(exist_ok=True)
        (ROOT / "gates/S0/artifacts/serving_check_selftest.json").write_text(json.dumps(out, indent=1) + "\n")
