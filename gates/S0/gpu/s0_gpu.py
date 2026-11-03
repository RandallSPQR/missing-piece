"""Missing Piece S0-GPU, run ON THE POD for one model (rules: gates/S0/S0_GPU_PLAN.md and gates/S0/serving_check.py,
fixed before any call). Subcommands (the driver calls them in this order, each against the server it has just started):

  part1  M OUT --start J      v1.3.0 strict server. Token-level agreement of the canonical serializer's ids with the
                              official template's ids on every Missing Piece context shape (CPU-side, real tokenizer);
                              single-token options; stop ids; 8-repeat bit-identity and exact-fallback consistency on
                              three multi-turn Missing Piece vote prompts; StPT's three S0 prompts read for the
                              v1.2.0 link check.
  c3     M OUT MODE --start J 8 development quads (32 games, 4 rounds, probes on): strict = sequential; throughput
                              modes = lockstep cohorts of 32. Same plans and seeds in every mode (paired games).
                              The strict run also writes the 64 vote prompts C1/C2 use.
  c12    M OUT MODE --start J C1 cold vs warm prefix cache (POST /reset_prefix_cache; server in VLLM_SERVER_DEV_MODE) and
                              C2 alone vs inside a cohort of 32 concurrent readouts, on the 64 vote prompts.
  summary M OUT               per-model verdicts (C3 per model; the pooled C3 rule is applied after all models,
                              gates/S0/gpu/analyse.py).
--mock runs every path with the CPU mock backend (no server, no tokenizer) to test the code before any spend."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gates/S0"))
from mp import manifest as mf  # noqa: E402
from mp.protocol import Settings  # noqa: E402
from mp.runner import run_lockstep  # noqa: E402
from serving_check import FLIP_NATS, MAX_NATS, FLIP_SHARE, dev_games, game_compare, readout_deltas  # noqa: E402

BASE = "http://localhost:8000"
N_QUADS, N_PROMPTS, COHORT = 8, 64, 32


def dump(obj, path):
    Path(path).write_text(json.dumps(obj, indent=1, default=str) + "\n")


def start_id(j):
    return mf.server_start_id(os.environ.get("RUNPOD_POD_ID", "local"), j, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def backend(model, mock):
    if mock:
        from mp.backend import MockBackend
        return MockBackend(model), None
    import sae_ethos_pipeline  # noqa: F401
    import lineup
    import modelcfg
    from transformers import AutoTokenizer
    from mp.backend import VLLMBackend
    e = lineup.models()[model]
    tok = AutoTokenizer.from_pretrained(e["hf_id"], revision=e["revision"])
    served = modelcfg.models()["endpoint"]["served_model_name"]
    return VLLMBackend(model, tok, base_url=BASE + "/v1", served_name=served), tok


def header(model, mode, j, mock):
    return mf.header(model, start_id(j), require_pipeline=not mock, serving_mode=mode, validating=mode != "strict")


# ---------------- part 1 ----------------
def part1(model, out, j, mock):
    be, tok = backend(model, mock)
    res = {"manifest": header(model, "strict", j, mock)}
    from mp.assign import make_plan
    from mp.protocol import Game
    spec = json.loads((ROOT / "gates/S1/banks/development/mp-dev-clinic-nurse-cert-A.json").read_text())

    class Cap:   # build every context shape with mock text, then compare token ids with the real tokenizer
        def __init__(self, inner):
            self.i, self.seen = inner, []
            self.serialize, self.prompt_sha256 = inner.serialize, inner.prompt_sha256

        def generate(self, m, **k):
            self.seen.append(m); return self.i.generate(m, **k)

        def readout(self, m):
            self.seen.append(m); return self.i.readout(m)

    from mp.backend import MockBackend
    cap = Cap(MockBackend(model))
    Game(spec, make_plan(spec, model, 0, 4, tag="s0gpu"), "KP", cap,
         Settings(probe_labels="all", probe_rounds="every")).run(probes=True)
    vote_prompts = [m for m in cap.seen if "Private vote" in m[-1]["content"]][:3]
    if mock:
        res["token_agreement"] = {"checked": len(cap.seen), "agree": len(cap.seen), "mock": True}
        res["live"] = {"mock": True}
        dump(res, out); return res
    import sae_ethos_pipeline  # noqa: F401
    import modelcfg
    from lineup import readout
    ser = modelcfg.serializer()
    kw = dict(modelcfg.target().get("chat_template_kwargs") or {})
    agree, bad = 0, []
    for m in cap.seen:
        ours = list(ser.apply_to_tokenizer(tok, m, add_generation_prompt=True))
        t = tok.apply_chat_template(m, tokenize=True, add_generation_prompt=True, **kw)
        theirs = list(t["input_ids"] if hasattr(t, "keys") else t)
        if theirs and isinstance(theirs[0], list):
            theirs = theirs[0]
        if ours == theirs:
            agree += 1
        elif len(bad) < 3:
            k = next((i for i, (a, b) in enumerate(zip(ours, theirs)) if a != b), min(len(ours), len(theirs)))
            bad.append({"len_ours": len(ours), "len_template": len(theirs), "first_diff": k})
    res["token_agreement"] = {"checked": len(cap.seen), "agree": agree, "examples": bad}
    res["check_tokenizer"] = modelcfg.check_tokenizer(tok)
    opt = readout.option_token_ids(tok)
    res["option_token_ids"] = opt
    t, served = readout.HTTPTransport(BASE + "/v1"), modelcfg.models()["endpoint"]["served_model_name"]
    live = {}
    for i, m in enumerate(vote_prompts):
        ids = ser.apply_to_tokenizer(tok, m)
        live[f"mp_vote_{i}"] = {"n_prompt_tokens": len(ids), "readout": readout.readout(t, served, ids, opt),
                                "repeat_probe": readout.repeat_probe(t, served, ids, opt, n=8),
                                "fallback_consistency": readout.fallback_consistency(t, served, ids, opt)}
    stpt = {"plain": "Two options, A and B. Evidence: the left door is warm. Answer with one letter: A or B.",
            "board": "Your evidence: the left door is warm.\nYour current vote: B.\nYour contacts' votes: A, B, A, A.\n\nWhich option do you vote for now? Answer with one letter: A or B.",
            "lopsided": "Option A is correct. Answer with one letter: A or B."}
    link = {k: readout.readout(t, served, ser.apply_to_tokenizer(tok, [{"role": "user", "content": v}]), opt)
            for k, v in stpt.items()}
    res["live"] = live
    res["link_check_readouts"] = link
    res["pass"] = bool(agree == len(cap.seen) and all(v["repeat_probe"]["bit_identical"] and v["fallback_consistency"]["ok"]
                                                       for v in live.values()))
    dump(res, out)
    print(json.dumps({"token_agree": f"{agree}/{len(cap.seen)}", "repeats": [v["repeat_probe"]["bit_identical"] for v in live.values()],
                      "fallback": [v["fallback_consistency"]["ok"] for v in live.values()], "pass": res["pass"]}))
    return res


# ---------------- C3 ----------------
def c3(model, out, mode, j, mock):
    be, _ = backend(model, mock)
    s = Settings()
    head = header(model, mode, j, mock)
    games = dev_games(model, N_QUADS, be, s)
    sid = head.get("server_start", {}).get("id")
    for g in games:
        g.plan.start_id = sid
    t0 = time.time()
    if mode == "strict":
        recs, batches = [g.run(probes=True) for g in games], []
    else:
        r = run_lockstep(games, be, probes=True, max_concurrency=COHORT)
        recs, batches = r["records"], r["batches"]
    res = {"manifest": head, "mode": mode, "wall_s": round(time.time() - t0, 1), "records": recs, "batches": batches}
    dump(res, out)
    if mode == "strict":     # the vote prompts for C1/C2, taken from these development games
        vp = []
        for g in games:
            for me in range(1, 6):
                vp.append(g.context(me, len(g.events), g.W["vote"].format(question_block=g.qblock)))
        dump(vp[:N_PROMPTS], Path(out).with_name(f"vote_prompts_{model}.json"))
    print(json.dumps({"mode": mode, "games": len(recs), "wall_s": res["wall_s"],
                      "mean_support": sum(r["receiver_support"] for r in recs) / len(recs)}))
    return res


# ---------------- C1 / C2 ----------------
def reset_cache(mock):
    if mock:
        return 200
    req = urllib.request.Request(BASE + "/reset_prefix_cache", method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def c12(model, out, mode, j, mock):
    be, _ = backend(model, mock)
    prompts = json.loads(Path(out).with_name(f"vote_prompts_{model}.json").read_text())
    head = header(model, mode, j, mock)
    cold, warm = [], []
    for m in prompts:
        reset_cache(mock)
        cold.append(be.readout(m))
        warm.append(be.readout(m))
    alone = [be.readout(m) for m in prompts]                     # cache warm for every prompt now
    with ThreadPoolExecutor(max_workers=COHORT) as pool:
        cohort = []
        for i in range(0, len(prompts), COHORT):
            cohort += list(pool.map(be.readout, prompts[i:i + COHORT]))
    c1, c2 = readout_deltas(cold, warm), readout_deltas(alone, cohort)
    c1["pass"] = c1["max_abs_nats"] <= MAX_NATS and c1["share_logit_delta_gt_0.05"] <= FLIP_SHARE
    c2["pass"] = c2["all_zero"] if mode == "throughput_invariant" else (c2["max_abs_nats"] <= MAX_NATS and
                                                                         c2["share_logit_delta_gt_0.05"] <= FLIP_SHARE)
    strip = lambda L: [{k: v for k, v in x.items() if k in ("logp", "p", "non_option_mass", "read_by")} for x in L]  # noqa: E731
    res = {"manifest": head, "mode": mode, "C1": c1, "C2": c2, "rules": {"max_nats": MAX_NATS, "flip_nats": FLIP_NATS,
           "flip_share": FLIP_SHARE}, "readouts": {"cold": strip(cold), "warm": strip(warm), "alone": strip(alone),
                                                  "cohort": strip(cohort)}}
    dump(res, out)
    print(json.dumps({"mode": mode, "C1": c1, "C2": c2}))
    return res


def summary(model, outdir):
    d = Path(outdir)
    ld = lambda f: json.loads((d / f).read_text()) if (d / f).exists() else None  # noqa: E731
    p1, strict = ld(f"part1_{model}.json"), ld(f"c3_strict_{model}.json")
    s = {"model": model, "part1_pass": p1 and p1.get("pass"),
         "token_agreement": p1 and p1.get("token_agreement")}
    for mode in ("throughput", "throughput_invariant"):
        c12r, c3r = ld(f"c12_{mode}_{model}.json"), ld(f"c3_{mode}_{model}.json")
        s[mode] = {"server_started": bool(c12r or c3r),
                   "C1": c12r and c12r["C1"], "C2": c12r and c12r["C2"],
                   "C3_model": game_compare(strict["records"], c3r["records"]) if (strict and c3r) else None}
    (d / f"summary_{model}.json").write_text(json.dumps(s, indent=1, default=str) + "\n")
    print(json.dumps(s, default=str)[:1500])
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["part1", "c3", "c12", "summary"])
    ap.add_argument("model"); ap.add_argument("out"); ap.add_argument("mode", nargs="?", default="strict")
    ap.add_argument("--start", type=int, default=0); ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    if a.cmd == "part1":
        part1(a.model, a.out, a.start, a.mock)
    elif a.cmd == "c3":
        c3(a.model, a.out, a.mode, a.start, a.mock)
    elif a.cmd == "c12":
        c12(a.model, a.out, a.mode, a.start, a.mock)
    else:
        summary(a.model, a.out)
