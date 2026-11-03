"""Batched serving (owner, 2026-11-03, cost reduction): run many games in parallel, with the four cells of each quad
interleaved in the same batches, and record batch composition.

run_lockstep advances a set of games call by call. At every step it collects the next pending call of every unfinished
game (one per game), submits them concurrently (up to `max_concurrency` at a time), and sends each result back to its
game. Because the four cells of a quad have the same call sequence (same speaking orders, same seeds), their k-th calls
always land in the same cohort, so cells share batches and any batch-composition effect is balanced across cells.

Recorded per cohort (`batches`): index, wall time, and members (game, call kind, agent label). Each game record also
carries the cohort of every call. NOTE: the client controls which requests are IN FLIGHT together; vLLM's scheduler
decides the actual forward-pass batches (continuous batching, prefill chunking). Unless the server runs in a
batch-invariant mode, a call's numerics can depend on what else is in flight, so outputs are reproducible only in
distribution, not bit for bit (see gates/S0/S0_GPU_PLAN.md)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor


def _call(backend, call):
    t = time.time()
    res = backend.generate(call.messages, **call.gen) if call.kind == "generate" else backend.readout(call.messages)
    res = dict(res)
    res.setdefault("latency_s", round(time.time() - t, 4))
    return res


def run_lockstep(games, backend, probes: bool = True, max_concurrency: int = 32) -> dict:
    """games: mp.protocol.Game objects (typically the 4 cells of several quads, one model, one server start)."""
    gens = {id(g): g.steps(probes) for g in games}
    pending, results, batches = {}, {}, []
    for g in games:
        try:
            pending[id(g)] = (g, next(gens[id(g)]))
        except StopIteration as e:
            results[id(g)] = e.value
    cohort = 0
    with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        while pending:
            items = list(pending.values())
            for start in range(0, len(items), max_concurrency):       # a step larger than the cap is split
                chunk = items[start:start + max_concurrency]
                t0 = time.time()
                for g, _ in chunk:
                    g.cohort = cohort
                futs = [(g, call, pool.submit(_call, backend, call)) for g, call in chunk]
                outs = [(g, call, f.result()) for g, call, f in futs]
                batches.append({"cohort": cohort, "wall_s": round(time.time() - t0, 4), "size": len(chunk),
                                "members": [{"game_id": f"{g.plan.quad_id}/{g.cell}", "kind": c.tag.get("kind"),
                                             "label": c.tag.get("label"), "call": c.kind} for g, c, _ in outs]})
                for g, call, res in outs:
                    try:
                        pending[id(g)] = (g, gens[id(g)].send(res))
                    except StopIteration as e:
                        results[id(g)] = e.value
                        pending.pop(id(g), None)
                cohort += 1
    recs = [results[id(g)] for g in games]
    for r in recs:
        r["serving_mode"] = "lockstep"
    return {"records": recs, "batches": batches}
