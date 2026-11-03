"""Cost model for Missing Piece games (owner, 2026-11-03: report what S6 assumed, recompute; then, before any tier is
chosen, recompute again from the S4 pilot's MEASURED per-call costs: `measured_costs()` below).

Part A, measured on CPU: token counts of real Missing Piece contexts.
  Games are built by the real engine on the development bank with a mock backend that writes band-length messages from
  the bank's own vocabulary. Every call is serialised by the pipeline's qwen3_5 serializer and tokenised by the pinned
  Qwen3.5 tokenizer (tokenizer.json sha256 5f9e4d49..., the pipeline's recorded identity). Prefix-cache hits are
  simulated the way vLLM's automatic prefix caching works: a request reuses full 16-token blocks of the longest prefix
  it shares with any earlier request's prompt+output in the same server start (no eviction: a 96 GB card holds a
  start's working set at these sizes). Four protocol variants are counted:
    S6-as-filed   probes: all five agents after every round; no prefix caching
    new probes    probes: receivers only, midpoint + final round (owner)
    + caching     new probes, automatic prefix caching
    (batching changes time per token, not token counts)
Part B, assumed: GPU time from token counts. Sequential = S6's assumption (batch size 1): per-call prefill of uncached
  tokens at the prefill rate plus decode at the single-stream rate. Batched = lockstep cohorts of 16+ in flight: decode
  aggregate throughput x speedup; prefill unchanged (compute-bound). Batch-invariant kernels: a throughput penalty.
  ALL rates and speedups here are assumptions, bracketed low/high; the S4 pilot measures them.
Part C, grading: Paper 1's graders via OpenRouter (primary anthropic/claude-sonnet-4.5 and gate grader
  google/gemini-2.5-flash on the same items; no batch discount on this route), the rubric as a cached prefix for the
  primary, speaker messages on every quad (P14), other measures on a seeded 50% quad subsample.

Writes gates/S6/results/cost_model.json and cost_model.md."""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mp.assign import make_plan  # noqa: E402
from mp.backend import MockBackend  # noqa: E402
from mp.protocol import Game, Settings  # noqa: E402
from mp.runner import run_lockstep  # noqa: E402

TOKENIZER = Path("/tmp/claude-0/-home-user/c33b92ab-3163-5d4d-bb33-9391ff19d3c0/scratchpad/tok/tokenizer.json")
BLOCK = 16


class BandMock(MockBackend):
    """Messages of realistic length (80-110 words) drawn from the bank's own words; exit polls 20-35 words."""

    def __init__(self, model, vocab):
        super().__init__(model)
        self.vocab = vocab

    def generate(self, messages, seed, max_tokens, temperature, top_p):
        out = super().generate(messages, seed, max_tokens, temperature, top_p)
        if max_tokens > 8:
            rng = self._rng(messages, seed)
            n = rng.randint(80, 110) if max_tokens > 150 else rng.randint(20, 35)
            out["text"] = " ".join(rng.choice(self.vocab) for _ in range(n))
        return out


class Recorder:
    """Wraps a backend and logs every request in submission order: serialised prompt and output text."""

    def __init__(self, be):
        self.be, self.log = be, []
        self.prompt_sha256 = be.prompt_sha256
        self.serialize = be.serialize

    def generate(self, messages, **kw):
        out = self.be.generate(messages, **kw)
        self.log.append((self.be.serialize(messages), out["text"], kw["max_tokens"]))
        return out

    def readout(self, messages):
        out = self.be.readout(messages)
        self.log.append((self.be.serialize(messages), "", 1))
        return out


def lcp(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def count(log, tok, caching: bool):
    seen, tot = [], {"prompt": 0, "uncached_prompt": 0, "output": 0, "calls": 0}
    for prompt, text, mx in log:
        p = tok.encode(prompt, add_special_tokens=False).ids
        o = tok.encode(text, add_special_tokens=False).ids if text else [0]
        hit = 0
        if caching:
            for s in seen[-400:]:                      # recent requests: same games and same start
                if s[0] == p[0]:
                    hit = max(hit, lcp(p, s))
            hit = (hit // BLOCK) * BLOCK
            hit = min(hit, len(p) - 1)                 # the last prompt token is always computed
        tot["prompt"] += len(p)
        tot["uncached_prompt"] += len(p) - hit
        tot["output"] += len(o)
        tot["calls"] += 1
        seen.append(p + o)
    return tot


def measure(n_quads=8, model="qwen3.5-9b"):
    import tokenizers
    tok = tokenizers.Tokenizer.from_file(str(TOKENIZER))
    specs = [json.loads(p.read_text()) for p in sorted((ROOT / "gates/S1/banks/development").glob("*.json"))
             if "challenge" not in p.name]
    vocab = sorted({w for sp in specs for it in sp["evidence_model"]["items"] for w in it["text"].split()})
    random.Random(0).shuffle(specs)
    out = {}
    for name, st in (("S6_as_filed", Settings(probe_labels="all", probe_rounds="every")), ("new_probes", Settings())):
        rec = Recorder(BandMock(model, vocab))
        games = [Game(sp, make_plan(sp, model, 0, st.rounds, tag="cost"), c, rec, st)
                 for sp in specs[:n_quads] for c in ("UA", "UP", "KA", "KP")]
        res = run_lockstep(games, rec, probes=True, max_concurrency=1)    # submission order = lockstep order
        n = len(games)
        words = [m["words"] for r in res["records"] for m in r["messages"]]
        for caching in (False, True):
            c = count(rec.log, tok, caching)
            out[f"{name}{'_cache' if caching else ''}"] = {k: round(v / n, 1) for k, v in c.items()}
        out[f"{name}_mean_message_words"] = round(sum(words) / len(words), 1)
    out["games_per_variant"] = n_quads * 4
    return out


# ---------------- Part B: time and money (assumptions) ----------------
A = {
    "usd_per_pod_hour": 2.49,          # as S6 (derived from StPT's approved S8 cap, D27); an upper estimate
    "small": {"decode_tps": 90, "prefill_tps": 8000, "load_min": 3, "n_models": 3},
    "large": {"decode_tps": 30, "prefill_tps": 2500, "load_min": 8, "n_models": 2},
    "request_overhead_s": 0.05,
    "batched_decode_speedup": {"low": 5, "mid": 8, "high": 12},     # aggregate decode throughput at ~16-32 in flight
    "invariant_throughput_factor": {"low": 0.4, "mid": 0.6, "high": 0.8},   # batch-invariant kernels (beta)
    "quads_per_start": 8,
}
GRADE = {   # Paper 1's graders via OpenRouter (owner 2026-11-03): no batch discount on this route
    "speaker_items_per_game": 4,      # graded on every quad (P14)
    "other_items_per_game": 7,        # ~2 verifier-holder messages + 5 exit polls, on the 50% quad subsample
    "subsample": 0.5,
    "content_tok_per_item": 260, "output_tok_per_item": 45,
    "rubric_tok": 1100,               # MP-R1 plus coded examples, sized to clear Sonnet 4.5's 1,024-token cache minimum
    "primary_usd": (3.00, 15.00),     # anthropic/claude-sonnet-4.5 (Paper 1 models.json price)
    "gate_usd": (0.30, 2.50),         # google/gemini-2.5-flash, on the same items (Paper 1's gate pair)
    "cache_read_factor": 0.1,         # primary rubric reads; the gate grader is costed uncached (conservative)
    "opus_as_filed_usd_per_game": 0.018,   # S6 as filed: Opus 5.5 batch, 6,000 in / 600 out, all games
}


def seconds_per_game(tokens: dict, size: str, batched: bool, invariant_factor: float = 1.0, speedup: float = 1.0):
    c = A[size]
    pre = tokens["uncached_prompt"] / c["prefill_tps"]
    dec = tokens["output"] / c["decode_tps"]
    ovh = tokens["calls"] * A["request_overhead_s"]
    if batched:
        dec, ovh = dec / speedup, ovh / speedup
        return (pre + dec + ovh) / invariant_factor
    return pre + dec + ovh


def grading_usd_per_game(cached: bool) -> float:
    g = GRADE
    items = g["speaker_items_per_game"] + g["other_items_per_game"] * g["subsample"]
    rub = g["rubric_tok"] * (g["cache_read_factor"] if cached else 1.0)
    prim = ((rub + g["content_tok_per_item"]) * g["primary_usd"][0] + g["output_tok_per_item"] * g["primary_usd"][1]) / 1e6
    gate = ((g["rubric_tok"] + g["content_tok_per_item"]) * g["gate_usd"][0] + g["output_tok_per_item"] * g["gate_usd"][1]) / 1e6
    return items * (prim + gate)


def tier_costs(tokens: dict, stories: int, reps: int = 1) -> dict:
    games_per_model = stories * 2 * 4 * reps
    starts = math.ceil(stories * 2 * reps / A["quads_per_start"])
    variants = {
        "S6_as_filed (sequential, no cache, all probes, Opus all games)": ("S6_as_filed", False, None, None, "opus"),
        "new probes (sequential, no cache)": ("new_probes", False, None, None, "sonnet"),
        "new probes + prefix caching (sequential)": ("new_probes_cache", False, None, None, "sonnet"),
        "new probes + caching + batched": ("new_probes_cache", True, "batched", None, "sonnet"),
        "new probes + caching + batched, batch-invariant": ("new_probes_cache", True, "batched", "inv", "sonnet"),
    }
    out = {}
    for label, (key, batched, _, inv, grader) in variants.items():
        row = {}
        for lvl in ("low", "mid", "high") if batched else ("mid",):
            sp = A["batched_decode_speedup"][lvl]
            f = A["invariant_throughput_factor"][lvl] if inv else 1.0
            gpu_h = 0.0
            for size in ("small", "large"):
                s = seconds_per_game(tokens[key], size, batched, f, sp)
                gpu_h += A[size]["n_models"] * (games_per_model * s / 3600 + starts * A[size]["load_min"] / 60)
            games = games_per_model * 5
            grade = games * (GRADE["opus_as_filed_usd_per_game"] if grader == "opus" else grading_usd_per_game(True))
            row[lvl] = {"gpu_hours": round(gpu_h, 1), "gpu_usd": round(gpu_h * A["usd_per_pod_hour"]),
                        "grading_usd": round(grade), "total_usd": round(gpu_h * A["usd_per_pod_hour"] + grade)}
        out[label] = row
    return out


def measured_costs(records: list[dict], batches: list[dict], model_size: str) -> dict:
    """S4 pilot: per-game GPU seconds from the lockstep cohorts' wall time, and per-call token usage reported by the
    server (prompt, cached, completion). Feed the result to tier_costs in place of the assumed rates (item 5)."""
    games = len(records)
    wall = sum(b["wall_s"] for b in batches)
    calls = [c for r in records for c in r["live_calls"] + r.get("live_readouts", []) + r["probes"]]
    u = [c.get("usage") or {} for c in calls]
    return {"model_size": model_size, "games": games, "gpu_seconds_per_game": wall / games if games else None,
            "prompt_tokens_per_game": sum(x.get("prompt_tokens") or 0 for x in u) / games,
            "cached_tokens_per_game": sum(x.get("cached_tokens") or 0 for x in u) / games,
            "completion_tokens_per_game": sum(x.get("completion_tokens") or 0 for x in u) / games}


def main():
    tokens = measure()
    tiers = {K: tier_costs(tokens, K) for K in (24, 26, 30, 36, 48, 60, 72)}
    out = {"tokens_per_game_measured_cpu": tokens, "assumptions": A, "grading": GRADE,
           "grading_usd_per_game": {"opus_as_filed": GRADE["opus_as_filed_usd_per_game"],
                                     "paper1_graders_openrouter_cached": round(grading_usd_per_game(True), 5),
                                     "paper1_graders_openrouter_uncached": round(grading_usd_per_game(False), 5)},
           "tiers_1_replicate": tiers}
    (ROOT / "gates/S6/results").mkdir(exist_ok=True)
    (ROOT / "gates/S6/results/cost_model.json").write_text(json.dumps(out, indent=1) + "\n")
    t = tokens
    md = ["| protocol variant | prompt tokens / game | uncached prompt tokens / game | output tokens / game | calls / game |",
          "|---|---|---|---|---|"]
    for k in ("S6_as_filed", "S6_as_filed_cache", "new_probes", "new_probes_cache"):
        md.append(f"| {k} | {t[k]['prompt']:,.0f} | {t[k]['uncached_prompt']:,.0f} | {t[k]['output']:,.0f} | {t[k]['calls']:.0f} |")
    md += ["", "| stories (1 replicate) | variant | GPU h (mid) | total $ (low / mid / high) |", "|---|---|---|---|"]
    for K, rows in tiers.items():
        for label, r in rows.items():
            tot = " / ".join(str(r[l]["total_usd"]) for l in ("low", "mid", "high") if l in r)
            md.append(f"| {K} | {label} | {r['mid']['gpu_hours']} | {tot} |")
    (ROOT / "gates/S6/results/cost_model.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:7]))
    print(json.dumps(out["grading_usd_per_game"]))
    for K in (30, 72):
        for label, r in tiers[K].items():
            print(K, label, r["mid"])


if __name__ == "__main__":
    main()
