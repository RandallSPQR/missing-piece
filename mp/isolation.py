"""Branch isolation (brief: "verify live contexts are byte-identical with and without probing").

For each game, run it twice with the same plan and backend state: once without probes, once with the private conviction
probe after every round. Every live call (messages, votes, exit polls) must have the same serialised prompt (sha256)
and the same output, in the same order. A NEGATIVE CONTROL runs the same game with a deliberately leaky probe (its
trace is written into the event list); the check must detect it. On CPU this uses the mock backend; on GPU the same
function runs against one server start (S4), where outputs are deterministic for a fixed seed."""
from __future__ import annotations

from mp.protocol import Settings, run_game


def live_trace(rec):
    return [(c["label"], c["kind"], c["prompt_sha256"], c["text"]) for c in rec["live_calls"]]


def check(spec, plan, cell, backend_factory, settings: Settings | None = None) -> dict:
    s = settings or Settings()
    a = run_game(spec, plan, cell, backend_factory(), s, probes=False)
    b = run_game(spec, plan, cell, backend_factory(), s, probes=True)
    c = run_game(spec, plan, cell, backend_factory(), s, probes=True, leaky_probes=True)
    ta, tb, tc = live_trace(a), live_trace(b), live_trace(c)
    return {"game": a["game_id"], "live_calls": len(ta), "probes_run": len(b["probes"]),
            "identical_with_probes": ta == tb,
            "negative_control_detected": ta != tc,
            "first_divergence_control": next((i for i, (x, y) in enumerate(zip(ta, tc)) if x != y), None)}
