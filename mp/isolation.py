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


def check_lockstep(games_factory, backend_factory) -> dict:
    """Lockstep (batched) variant: the same set of games run in lockstep cohorts with and without probes, and with a
    leaky negative control. On CPU the mock backend's outputs do not depend on batch composition, so this checks the
    STRUCTURAL isolation of the batched runner; numerical isolation on GPU is S0-GPU's question."""
    from mp.runner import run_lockstep
    a = run_lockstep(games_factory(False), backend_factory(), probes=False)["records"]
    b = run_lockstep(games_factory(False), backend_factory(), probes=True)["records"]
    c = run_lockstep(games_factory(True), backend_factory(), probes=True)["records"]
    ta, tb, tc = ([live_trace(r) for r in x] for x in (a, b, c))
    return {"games": len(ta), "identical_with_probes": ta == tb, "negative_control_detected": ta != tc}
