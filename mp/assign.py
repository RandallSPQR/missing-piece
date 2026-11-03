"""Paired assignment and server-start blocking.

One QUAD = (scenario, model, replicate): the four cells share one GamePlan (labels, verifier holder, neutral records,
letter mapping, speaking orders, call seeds), so cell contrasts are within-quad; and the four cells of a quad always run
within ONE server start (D14, carry-over 1), in a seeded random cell order. Within each server start the letter mapping
of the report option (F displayed as A or as B) is balanced by seeded permuted blocks (D20 item 4). Truths are balanced
by construction (each story gives a truth-A and a truth-B scenario)."""
from __future__ import annotations

import random

from mp.protocol import GamePlan, seed_of


def make_plan(spec: dict, model: str, replicate: int, rounds: int, tag: str = "mp", F_letter: str | None = None) -> GamePlan:
    s = seed_of(tag, "plan", spec["scenario_id"], model, replicate)
    rng = random.Random(s)
    labels = [1, 2, 3, 4, 5]
    speaker = rng.choice(labels)
    receivers = [k for k in labels if k != speaker]
    vh = rng.choice(receivers)
    neutral_ids = [f"neutral{k}" for k in range(5)]
    rng.shuffle(neutral_ids)
    neutral_of = dict(zip(labels, neutral_ids))
    F = spec["evidence_model"]["report_option"]
    if F_letter is None:
        F_letter = rng.choice("AB")
    letter_of = {F: F_letter, ("B" if F == "A" else "A"): ("B" if F_letter == "A" else "A")}
    orders = []
    for _ in range(rounds):
        o = labels[:]
        rng.shuffle(o)
        orders.append(o)
    cell_order = ["UA", "UP", "KA", "KP"]
    rng.shuffle(cell_order)
    return GamePlan(quad_id=f"{spec['scenario_id']}/{model}/r{replicate}", scenario_id=spec["scenario_id"], model=model,
                    replicate=replicate, speaker=speaker, verifier_holder=vh, neutral_of=neutral_of,
                    letter_of=letter_of, orders=orders, seed_root=seed_of(tag, "calls", s), cell_order=cell_order)


def schedule(specs: list[dict], model: str, n_rep: int, quads_per_start: int, rounds: int, tag: str = "mp") -> list[dict]:
    """Assign quads to server starts for one model: seeded shuffle of (scenario, replicate); consecutive blocks of
    `quads_per_start` form one start; within each start, F's display letter alternates over a seeded permutation so it
    is balanced (+-1) within the start."""
    rng = random.Random(seed_of(tag, "schedule", model))
    units = [(sp, r) for sp in specs for r in range(n_rep)]
    rng.shuffle(units)
    out = []
    for b in range(0, len(units), quads_per_start):
        block = units[b:b + quads_per_start]
        letters = (["A", "B"] * ((len(block) + 1) // 2))[:len(block)]
        rng.shuffle(letters)
        for (sp, r), L in zip(block, letters):
            plan = make_plan(sp, model, r, rounds, tag, F_letter=L)
            out.append({"start_block": b // quads_per_start, "plan": plan, "spec": sp})
    return out
