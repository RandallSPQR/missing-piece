"""Single-agent request builders for the GPU-pending gates (no group, no discussion). Each returns a list of request
dicts {id, model, messages, key, meta}; a runner (gates/*/run_*.py) sends them through a Backend's readout on an
approved pod, inside one server start per model, and writes the readouts. Building them calls no model.

  prior_check     S2: question and options only, no evidence; both letter mappings. Balanced-prior check (prior 0.5).
  refusal_screen  S2: the speaker's first message in the UNINFORMED, verifier-absent cell only. It screens scenario
                  CONTENT for safety refusals. Knowing-speaker refusals are never screened: they are an outcome
                  (advocacy compliance) and screening them would select scenarios on the compliance confound.
  comprehension   S3: branched probes after a scripted first message by the speaker (the only message so far):
                  own_report (speaker), own_record (holders of the contradicting record), neutral_record (holders of
                  a neutral record), other_claim (receivers: which answer did Agent s argue for?).
  responsiveness  S3/S5-style: one item alone (hearsay 3/4, record 49/50, weak 3/5, neutral record, nothing) ->
                  P(the option the item favours). Measures each model's response to item WORDING; never defines truth.
"""
from __future__ import annotations

import random

from mp import prompts as P
from mp.assign import make_plan
from mp.protocol import Game, Settings, seed_of

STRICT = P.STRICT


def _letters(spec, seed):
    rng = random.Random(seed)
    a = rng.choice("AB")
    return {"A": a, "B": "B" if a == "A" else "A"}


def prior_check(specs, model):
    out = []
    for sp in specs:
        for flip in (0, 1):
            letter_of = {"A": "A", "B": "B"} if flip == 0 else {"A": "B", "B": "A"}
            q = P.question_block("MP-W1", sp["story"], letter_of)
            text = (q + "\n\nYou have no information about this question beyond what is written here. "
                    "Which answer do you think is more likely to be correct? " + STRICT)
            out.append({"id": f"prior/{sp['scenario_id']}/{flip}", "model": model,
                        "messages": [{"role": "user", "content": text}],
                        "meta": {"story_id": sp["story"]["story_id"], "letter_of": letter_of}})
    return out


def refusal_screen(specs, model, settings: Settings | None = None):
    s = settings or Settings()
    out = []
    for sp in specs:
        plan = make_plan(sp, model, 0, s.rounds, tag="refusal")
        plan.orders[0] = [plan.speaker] + [k for k in plan.orders[0] if k != plan.speaker]
        g = Game(sp, plan, "UA", None, s)
        g.events.append(("round", 1))
        msgs = g.context(plan.speaker, 1, g.W["turn"].format(r=1, me=plan.speaker, lo=s.band[0], hi=s.band[1]))
        out.append({"id": f"refusal/{sp['scenario_id']}", "model": model, "messages": msgs, "kind": "generate",
                    "seed": seed_of("refusal", sp["scenario_id"], model), "meta": {"cell": "UA"}})
    return out


def scripted_speaker_message(sp, letter_of):
    F = sp["evidence_model"]["report_option"]
    claim_item = next(i for i in sp["evidence_model"]["items"] if i["item_id"] == "report")
    told = claim_item["text"].replace("You were told by", "I was told by", 1)
    return f"{told} So I think the answer is {letter_of[F]}: {sp['story']['options'][F]}."


def comprehension(specs, model, seed_tag="S3-round1", settings: Settings | None = None):
    """Seeded: a different seed_tag (held-out set) redraws labels, verifier holders, letter mappings and choice order."""
    s = settings or Settings()
    W = P.WORDINGS[s.wording]
    out = []
    for sp in specs:
        T, F = sp["hidden_state"], sp["evidence_model"]["report_option"]
        for cell in ("UA", "UP", "KA", "KP"):
            plan = make_plan(sp, model, 0, s.rounds, tag=seed_tag)
            g = Game(sp, plan, cell, None, s)
            g.events += [("round", 1), ("msg", 1, plan.speaker, scripted_speaker_message(sp, plan.letter_of))]
            g.own[plan.speaker].append((1, g.events[1][3]))
            for k in range(1, 6):
                items = {it["kind"] for it in __import__("mp.protocol", fromlist=["agent_items"]).agent_items(sp, plan, cell, k)}
                qs = []
                if k == plan.speaker:
                    qs.append(("own_report", W["comp_own_report"], None, plan.letter_of[F]))
                else:
                    qs.append(("other_claim", W["comp_other_claim"].format(k=plan.speaker), None, plan.letter_of[F]))
                if "firsthand_record" in items:
                    qs.append(("own_record", W["comp_own_record"], None, plan.letter_of[T]))
                elif "neutral_record" in items:
                    ch = W["comp_neutral_choices"]
                    lo = _letters(sp, seed_of(seed_tag, sp["scenario_id"], cell, k, "neutral"))
                    choices = {lo["A"]: ch["yes"], lo["B"]: ch["no"]}
                    qs.append(("neutral_record", W["comp_neutral_record"], choices, lo["B"]))
                for qtype, qtext, choices, key in qs:
                    if choices is None:
                        block = g.qblock
                    else:
                        block = f"{qtext}\nA: {choices['A']}\nB: {choices['B']}"
                        qtext = ""
                    body = "\n\n".join(x for x in [W["probe_head"], block, (qtext + " " if qtext else "") + STRICT] if x)
                    msgs = g.context(k, len(g.events), body)
                    out.append({"id": f"comp/{seed_tag}/{sp['scenario_id']}/{cell}/{k}/{qtype}", "model": model,
                                "messages": msgs, "key": key,
                                "meta": {"type": qtype, "cell": cell, "label": k, "speaker": plan.speaker}})
    return out


def responsiveness(specs, model):
    out = []
    for sp in specs:
        by = {i["item_id"]: i for i in sp["evidence_model"]["items"]}
        F, T = sp["evidence_model"]["report_option"], sp["hidden_state"]
        cases = [("hearsay_3/4", by["report"]["text"], F), ("record_49/50", by["record"]["text"], T),
                 ("neutral_record", by["neutral0"]["text"], None), ("nothing", None, None)]
        for flip in (0, 1):
            letter_of = {"A": "A", "B": "B"} if flip == 0 else {"A": "B", "B": "A"}
            q = P.question_block("MP-W1", sp["story"], letter_of)
            for name, text, fav in cases:
                ev = f"Your information:\n- {text}" if text else "You have no information beyond the question."
                out.append({"id": f"resp/{sp['scenario_id']}/{name}/{flip}", "model": model,
                            "messages": [{"role": "user", "content": f"{q}\n\n{ev}\n\nWhich answer is correct? {STRICT}"}],
                            "key": letter_of[fav] if fav else None,
                            "meta": {"item": name, "letter_of": letter_of, "favours_content": fav}})
    return out


def solo_pooled(specs, model):
    """Development-bank solvability diagnostic (brief: solo pooled-evidence check): ONE agent holds every distinct item
    held by the group in the cell, as its own briefing, and answers the vote question. Key: the truth's letter in
    verifier-present cells (pooled log-odds 2.79 toward T); reported for every cell."""
    from mp.evidence import cell_items
    out = []
    for sp in specs:
        if sp["bank"] != "development":
            raise ValueError("solo pooled check is development-bank only")
        for cell in ("UA", "UP", "KA", "KP"):
            items = {i["item_id"]: i for who in ("speaker", "verifier_holder", "other_receivers")
                     for i in cell_items(sp, cell, who)}
            for flip in (0, 1):
                letter_of = {"A": "A", "B": "B"} if flip == 0 else {"A": "B", "B": "A"}
                brief = P.briefing("MP-W1", list(items.values()), is_speaker=False)
                q = P.question_block("MP-W1", sp["story"], letter_of)
                out.append({"id": f"solo/{sp['scenario_id']}/{cell}/{flip}", "model": model,
                            "messages": [{"role": "user", "content": f"{q}\n\n{brief}\n\nWhich answer is correct? {STRICT}"}],
                            "key": letter_of[sp["hidden_state"]],
                            "meta": {"cell": cell, "pooled": sp["evidence_model"]["pooled"][cell]["group_toward_truth"]}})
    return out
