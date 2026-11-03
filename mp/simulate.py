"""Synthetic game-level data with KNOWN effects, in the same record schema the game engine writes (the fields the
analysis reads). Used to validate the analysis code (sign recovery, null behaviour, paired assignment) and by the S6 power
simulation. Nothing here is a finding.

Generative model (probability scale, per game = one cell of one quad):
  p = base[V] + delta_K * (+1/2 uninformed, -1/2 knowing) + delta_KV * K * V(+-1/2)
      + u_story + u_scen + u_model + (b_story + b_scen) * K       (story/scenario intercepts and knowledge slopes)
      + c_start                                                     (server-start offset, shared by the quad's cells)
  game probability ~ Beta with mean p (p kept in [0.02, 0.98]) and variance sd_game^2 + sd_jitter^2 (discussion-level
  noise plus between-start numerical jitter, D14 / A16), so cell means, and hence every contrast, are exactly the
  designed values (no clipping bias);
  receivers' votes: Binomial(4, game probability); each receiver vote is invalid with probability `invalid`.
Cross-model correlation of the story slopes: b_story is drawn once per story and shared by all models with correlation
rho (rho = 1 is the worst case for the pooled test, carry-over 6).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CELLS = (("UA", 0, 0), ("UP", 0, 1), ("KA", 1, 0), ("KP", 1, 1))


@dataclass
class SimParams:
    n_stories: int = 26
    n_models: int = 5
    n_rep: int = 1
    quads_per_start: int = 8
    base_absent: float = 0.65        # support with an uninformed speaker, no verifier (proxy)
    verifier_effect: float = -0.25   # verifier present minus absent (proxy)
    delta_K: float = 0.10            # uninformed minus knowing (the estimand)
    delta_KV: float = 0.0            # knowledge effect, present minus absent
    sd_story: float = 0.10
    sd_scen: float = 0.05
    sd_model: float = 0.08
    sd_slope_story: float = 0.08     # between-story SD of the knowledge effect
    sd_slope_scen: float = 0.04
    sd_slope_int_story: float = 0.08
    rho: float = 1.0                 # cross-model correlation of story slopes
    sd_start: float = 0.01           # systematic start offsets (A16: <= 0.0043; generous)
    sd_game: float = 0.25            # discussion-level noise within cell
    sd_jitter: float = 0.056         # between-start numerical jitter in vote probability (Gemma-3-27B worst case, A16)
    invalid: float = 0.003           # per-vote invalid probability (non-A/B mass <= 0.003 under the strict instruction)


def simulate(p: SimParams, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    recs = []
    models = [f"m{i}" for i in range(p.n_models)]
    u_model = dict(zip(models, rng.normal(0, p.sd_model, p.n_models)))
    for k in range(p.n_stories):
        story = f"story{k:03d}"
        u_story = rng.normal(0, p.sd_story)
        common = rng.normal(0, p.sd_slope_story)
        b_story = {m: np.sqrt(p.rho) * common + np.sqrt(1 - p.rho) * rng.normal(0, p.sd_slope_story) for m in models}
        bi_story = rng.normal(0, p.sd_slope_int_story)
        for truth in "AB":
            scen = f"mp-{story}-{truth}"
            u_scen = rng.normal(0, p.sd_scen)
            b_scen = rng.normal(0, p.sd_slope_scen)
            for m in models:
                for r in range(p.n_rep):
                    recs.append({"_quad": (scen, m, r), "story": story, "scen": scen, "model": m, "rep": r,
                                 "mu": p.base_absent + u_story + u_scen + u_model[m],
                                 "slope": p.delta_K + b_story[m] + b_scen, "slope_int": p.delta_KV + bi_story})
    # server starts: per model, seeded shuffle of its quads into blocks
    out = []
    for m in models:
        mq = [q for q in recs if q["model"] == m]
        order = rng.permutation(len(mq))
        for pos, idx in enumerate(order):
            q = mq[idx]
            start = f"{m}/start{pos // p.quads_per_start}"
            c_start = _start_offset(start, p.sd_start)
            qid = f"{q['scen']}/{m}/r{q['rep']}"
            for cell, knowing, ver in CELLS:
                Kc = 0.5 if knowing == 0 else -0.5
                Vc = 0.5 if ver == 1 else -0.5
                mu = (q["mu"] + p.verifier_effect * (ver) + q["slope"] * Kc + q["slope_int"] * Kc * Vc + c_start)
                pr = _beta_draw(rng, float(np.clip(mu, 0.02, 0.98)), p.sd_game ** 2 + p.sd_jitter ** 2)
                votes = rng.random(4) < pr
                invalid = rng.random(4) < p.invalid
                out.append({"quad_id": qid, "scenario_id": q["scen"], "story_id": q["story"], "model": m,
                            "replicate": q["rep"], "start_id": start, "cell": cell, "knowing": knowing,
                            "verifier": ver, "receiver_support": float(np.sum(votes & ~invalid)) / 4.0,
                            "receiver_invalid": int(invalid.sum()), "challenge_set": False})
    return out


def _start_offset(start_id: str, sd: float) -> float:
    import hashlib
    h = int(hashlib.sha256(f"start|{start_id}".encode()).hexdigest()[:12], 16)
    return float(np.random.default_rng(h).normal(0, sd))


def _beta_draw(rng, mu: float, var: float) -> float:
    """A Beta draw with mean mu and variance var (capped at 90% of the Bernoulli maximum mu(1-mu))."""
    var = min(var, 0.9 * mu * (1 - mu))
    if var <= 0:
        return mu
    phi = mu * (1 - mu) / var - 1
    return float(rng.beta(mu * phi, (1 - mu) * phi))
