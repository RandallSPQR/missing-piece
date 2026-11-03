"""The Missing Piece game: one speaker, four receivers, R discussion rounds, a private vote, an exit poll.

Live contexts are REBUILT from the game's event list every time an agent is called, so what an agent sees is a pure
function of (its briefing, the events so far, its own earlier outputs). Probes (private conviction, comprehension) run
on forked copies of an agent's context and their answers are never written to the event list or to any live context:
they cannot return. `run_game(..., probes=False)` and `run_game(..., probes=True)` must therefore produce byte-identical
live prompts and outputs; `mp.isolation` checks exactly that (with a leaky negative control that must be detected).

Every model call goes through a Backend (mp.backend): serialize(messages) -> the canonical prompt string of the pinned
pipeline's serializer; generate(...) with an explicit seed; readout(...) -> exact P(A), P(B), non-A/B mass.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from mp import evidence as ev
from mp import prompts as P
from mp import screens

VOTE_RE = re.compile(r"^\s*([AB])\s*\.?\s*$")


@dataclass
class Settings:
    wording: str = "MP-W1"
    rounds: int = 4                 # pilot sets R (brief: start 4)
    band: tuple = (60, 120)         # message band in words (brief: start 60-120); out-of-band counted, not regenerated
    message_max_tokens: int = 320
    vote_temperature: float = 0.6
    vote_top_p: float = 0.9
    vote_max_tokens: int = 4
    vote_retries: int = 3
    message_temperature: float = 0.7  # discussion sampling; proposed, set before S4 (not in the brief)
    message_top_p: float = 0.95
    exit_max_tokens: int = 120
    probe_conviction: bool = True
    probe_comprehension: bool = False
    arm: str = "natural"            # natural (the 2 x 2) | no_comm (vote on own briefing) | disclosure (standardised
                                    # complete-evidence list, then vote; no discussion)


@dataclass
class GamePlan:
    """Everything random about one game, drawn once per (scenario, model, replicate) and SHARED by the four cells
    (paired assignment): labels, the verifier holder, neutral-record assignment, letter mapping, speaking orders and the
    per-call seed root. Only the briefing contents differ between cells."""
    quad_id: str
    scenario_id: str
    model: str
    replicate: int
    speaker: int                    # label 1-5
    verifier_holder: int            # a receiver label
    neutral_of: dict                # label -> neutral item id (all five; the record replaces it where held)
    letter_of: dict                 # content key -> display letter
    orders: list                    # one permutation of labels 1-5 per round
    seed_root: int
    start_id: str | None = None
    cell_order: list = field(default_factory=lambda: list(ev.CELLS))


def seed_of(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:15], 16)


def agent_items(spec: dict, plan: GamePlan, cell: str, label: int) -> list[dict]:
    by = {it["item_id"]: it for it in spec["evidence_model"]["items"]}
    role = ("speaker" if label == plan.speaker else
            "verifier_holder" if label == plan.verifier_holder else "other_receivers")
    ids = spec["evidence_model"]["holdings"][cell][role]
    return [by[plan.neutral_of[label]] if i == "N" else by[i] for i in ids]


def briefings(spec: dict, plan: GamePlan, cell: str, wording: str) -> dict:
    return {k: P.briefing(wording, agent_items(spec, plan, cell, k), k == plan.speaker) for k in range(1, 6)}


def words(text: str) -> int:
    return len(text.split())


class Game:
    def __init__(self, spec, plan: GamePlan, cell: str, backend, settings: Settings, leaky_probes: bool = False):
        self.spec, self.plan, self.cell, self.b, self.s = spec, plan, cell, backend, settings
        self.W = P.WORDINGS[settings.wording]
        self.brief = briefings(spec, plan, cell, settings.wording)
        self.events: list[tuple] = []          # ("round", r) | ("msg", r, label, text)
        self.own: dict = {k: [] for k in range(1, 6)}   # label -> [(event index of own msg, text)]
        self.calls: list[dict] = []            # live calls only: label, kind, prompt sha256, output
        self.probes: list[dict] = []           # never read by any live context
        self.leaky = leaky_probes              # NEGATIVE CONTROL ONLY: writes probe Q/A into the event list
        self.qblock = P.question_block(settings.wording, spec["story"], plan.letter_of)

    # ---- context construction (pure function of events) ----
    def _render(self, ev_slice) -> str:
        out = []
        for e in ev_slice:
            if e[0] == "round":
                out.append(self.W["round_marker"].format(r=e[1]))
            elif e[0] == "msg":
                out.append(self.W["message_line"].format(k=e[2], text=e[3]))
            elif e[0] == "leak":                       # only ever present under the negative control
                out.append(e[1])
        return "\n".join(out)

    def context(self, me: int, upto: int, final_prompt: str) -> list[dict]:
        """Agent `me`'s messages: the opening, then for each of its own earlier messages an assistant turn, with the
        events in between as user turns; ends with a user turn holding the new events up to `upto` + final_prompt."""
        msgs, start = [], 0
        head = P.opening(self.s.wording, me, self.s.rounds, self.spec["story"], self.plan.letter_of, self.brief[me],
                         self.s.arm)
        if self.s.arm == "disclosure":
            held = [it for k in range(1, 6) for it in agent_items(self.spec, self.plan, self.cell, k)]
            head += "\n\n" + P.disclosure_list(self.s.wording, held)
        first = True
        for idx, text in self.own[me]:
            if idx >= upto:
                break
            block = self._render(self.events[start:idx])
            prompt = self._turn_prompt_for(idx)
            u = "\n\n".join(x for x in ([head] if first else []) + [block, prompt] if x)
            msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": text}]
            first, start = False, idx + 1
        block = self._render(self.events[start:upto])
        u = "\n\n".join(x for x in ([head] if first else []) + [block, final_prompt] if x)
        msgs.append({"role": "user", "content": u})
        return msgs

    def _turn_prompt_for(self, idx) -> str:
        r, me = self.events[idx][1], self.events[idx][2]
        return self.W["turn"].format(r=r, me=me, lo=self.s.band[0], hi=self.s.band[1])

    # ---- live calls ----
    def _seed(self, *parts) -> int:
        return seed_of(self.plan.seed_root, *parts)   # NOT the cell: common random numbers across the four cells

    def _live(self, label, kind, msgs, **gen):
        out = self.b.generate(msgs, **gen)
        self.calls.append({"label": label, "kind": kind, "prompt_sha256": self.b.prompt_sha256(msgs),
                           "seed": gen.get("seed"), "text": out["text"], "finish_reason": out.get("finish_reason")})
        return out

    def run(self, probes: bool = False) -> dict:
        s = self.s
        if s.arm not in ("natural", "no_comm", "disclosure"):
            raise ValueError(s.arm)
        for r in range(1, (s.rounds if s.arm == "natural" else 0) + 1):
            self.events.append(("round", r))
            for me in self.plan.orders[r - 1]:
                prompt = self.W["turn"].format(r=r, me=me, lo=s.band[0], hi=s.band[1])
                msgs = self.context(me, len(self.events), prompt)
                out = self._live(me, "message", msgs, seed=self._seed("msg", r, me), max_tokens=s.message_max_tokens,
                                 temperature=s.message_temperature, top_p=s.message_top_p)
                text = out["text"].strip()
                self.own[me].append((len(self.events), text))
                self.events.append(("msg", r, me, text))
            if probes:
                self._probe_round(r)
        votes, exits = {}, {}
        for me in range(1, 6):
            vprompt = self.W["vote"].format(question_block=self.qblock)
            msgs = self.context(me, len(self.events), vprompt)
            votes[me] = self._vote(me, msgs)
            ex_msgs = msgs + [{"role": "assistant", "content": votes[me]["raw"]},
                              {"role": "user", "content": self.W["exit"]}]
            exits[me] = self._live(me, "exit", ex_msgs, seed=self._seed("exit", me), max_tokens=s.exit_max_tokens,
                                   temperature=s.message_temperature, top_p=s.message_top_p)["text"].strip()
        return self._record(votes, exits)

    def _vote(self, me, msgs) -> dict:
        s = self.s
        ro = self.b.readout(msgs)      # exact P(A), P(B), non-A/B mass where the serving path allows
        attempts = []
        for a in range(1 + s.vote_retries):
            out = self._live(me, "vote" if a == 0 else f"vote_retry{a}", msgs, seed=self._seed("vote", me, a),
                             max_tokens=s.vote_max_tokens, temperature=s.vote_temperature, top_p=s.vote_top_p)
            attempts.append(out["text"])
            m = VOTE_RE.match(out["text"])
            if m:
                letter = m.group(1)
                content = {v: k for k, v in self.plan.letter_of.items()}[letter]
                return {"letter": letter, "content": content, "valid": True, "attempts": attempts, "raw": out["text"],
                        "readout": ro}
        return {"letter": None, "content": None, "valid": False, "attempts": attempts, "raw": attempts[-1],
                "readout": ro}

    # ---- branched probes ----
    def _probe_round(self, r):
        upto = len(self.events)
        F = self.spec["evidence_model"]["report_option"]
        for me in range(1, 6):
            q = self.W["probe_conviction"].format(question_block=self.qblock)
            branch = self.context(me, upto, q)            # a fresh list: the live context is never touched
            ro = self.b.readout(branch)
            pF = ro["p"][self.plan.letter_of[F]]
            pAB = ro["p"]["A"] + ro["p"]["B"]
            rec = {"round": r, "label": me, "kind": "conviction", "p_report_option": pF / pAB if pAB > 0 else None,
                   "non_ab_mass": ro["non_option_mass"], "prompt_sha256": self.b.prompt_sha256(branch)}
            self.probes.append(rec)
            if self.leaky:                                # negative control: a probe that DOES return
                self.events.append(("leak", f"(Agent {me} privately answered a question.)"))

    # ---- output ----
    def _record(self, votes, exits) -> dict:
        F = self.spec["evidence_model"]["report_option"]
        receivers = [k for k in range(1, 6) if k != self.plan.speaker]
        n_support = sum(1 for k in receivers if votes[k]["valid"] and votes[k]["content"] == F)
        n_invalid = sum(1 for k in receivers if not votes[k]["valid"])
        msgs = [{"round": e[1], "label": e[2], "text": e[3], "words": words(e[3]),
                 "in_band": self.s.band[0] <= words(e[3]) <= self.s.band[1],
                 "role_hidden": None} for e in self.events if e[0] == "msg"]
        return {
            "quad_id": self.plan.quad_id, "game_id": f"{self.plan.quad_id}/{self.cell}",
            "scenario_id": self.spec["scenario_id"], "story_id": self.spec["story"]["story_id"],
            "bank": self.spec["bank"], "challenge_set": self.spec["challenge_set"],
            "model": self.plan.model, "replicate": self.plan.replicate, "start_id": self.plan.start_id,
            "cell": self.cell, "knowing": int(self.cell[0] == "K"), "verifier": int(self.cell[1] == "P"),
            "wording": self.s.wording, "arm": self.s.arm,
            "rounds": self.s.rounds if self.s.arm == "natural" else 0, "band": list(self.s.band),
            "speaker": self.plan.speaker, "verifier_holder": self.plan.verifier_holder,
            "letter_of": self.plan.letter_of, "report_option": F, "orders": self.plan.orders,
            "messages": msgs,
            "votes": {str(k): {kk: v for kk, v in votes[k].items() if kk != "raw"} for k in votes},
            "exit_poll": {str(k): exits[k] for k in exits},
            "receiver_support": n_support / 4.0,               # invalid votes are not report votes; no exclusion
            "receiver_invalid": n_invalid,
            "speaker_vote_report": int(votes[self.plan.speaker]["valid"] and votes[self.plan.speaker]["content"] == F),
            "out_of_band": sum(1 for m in msgs if not m["in_band"]),
            "self_id_hits": screens.self_id(msgs + [{"text": t} for t in exits.values()]),
            "probes": self.probes,
            "live_calls": self.calls,
        }


def run_game(spec, plan, cell, backend, settings: Settings | None = None, probes=False, leaky_probes=False) -> dict:
    return Game(spec, plan, cell, backend, settings or Settings(), leaky_probes=leaky_probes).run(probes=probes)
