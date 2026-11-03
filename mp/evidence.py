"""Missing Piece evidence model (gate S1), on the shared evidence schema v1.0 (coordination record).

Every scenario fixes, before any model sees it:
  - a hidden state S in {A, B} (a CONTENT key of the scenario's own option table; display letters are mapped per game)
    and a prior P(S = A) = 0.5;
  - every evidence item, with a designed likelihood ratio fixed by its rendered text. Sources state their accuracy in
    plain frequencies (carry-over 5); a symmetric source right a of the time has LR = a / (1 - a) toward the option it
    favours. Items that favour neither option (neutral records, shared context) have LR 1;
  - the dependence structure: one item_id is one item however many agents hold it (the knowing speaker and the verifier
    holder hold the SAME record, counted once); a declared dependence group counts once (its strongest member);
  - the pooled-evidence benchmark per cell: prior log-odds + summed log LRs of the distinct items held by the group,
    signed toward the truth; and a prespecified solvability margin that verifier-present cells must reach.

Missing Piece items (all cells use the same report text, word for word):
  report   hearsay, held by the speaker in every cell; favours F (the false option); stated accuracy 3/4 (LR 3)
  record   firsthand, favours T (the truth); stated accuracy 49/50 (LR 49); held by the speaker in knowing cells and by
           one receiver in verifier-present cells
  neutral  firsthand records from the same source, matched in format and length to the record; LR 1
  shared   background sentences every agent holds; LR 1
  weak     (development challenge variants only) a shared weak report favouring F, 3/5 (LR 1.5): labelled
           conditional challenge set

Objective strength (the design LRs here) is kept apart from model responsiveness to wording, which is measured
(mp.responsiveness; never used to define truth).
"""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction

SCHEMA_VERSION = "1.0"
OPTIONS = ("A", "B")
CELLS = ("UA", "UP", "KA", "KP")          # knowledge (U uninformed / K knowing) x verifier (A absent / P present)
FREQ = {Fraction(3, 5): "3 times out of 5", Fraction(3, 4): "3 times out of 4", Fraction(9, 10): "9 times out of 10",
        Fraction(49, 50): "49 times out of 50"}

# Conventions proposed at S1 (owner to approve; see gates/S1/CONVENTIONS.md)
HEARSAY_ACCURACY = Fraction(3, 4)        # LR 3
RECORD_ACCURACY = Fraction(49, 50)       # LR 49
WEAK_ACCURACY = Fraction(3, 5)           # LR 1.5 (development challenge variants only)
POOLED_MARGIN = 2.2                      # log-odds toward the truth (posterior >= 0.90) in verifier-present cells

REPORT_SENTENCE = "You were told by {source}, who is right about matters like this {freq}, that {claim}."
RECORD_SENTENCE = "You checked {source} yourself, which is right about matters like this {freq}. It shows that {fact}."
WEAK_SENTENCE = "Everyone in the group has heard from {source}, who is right about matters like this {freq}, that {claim}."


def other(o: str) -> str:
    return "B" if o == "A" else "A"


def lr_of(accuracy) -> float:
    a = float(Fraction(accuracy))
    if not 0.5 < a < 1.0:
        raise ValueError(f"accuracy {a} must be in (0.5, 1)")
    return a / (1.0 - a)


def item_lr(item: dict) -> float:
    return 1.0 if item["favours"] == "neutral" else lr_of(item["accuracy"])


def pooled_logodds(items: list[dict], prior: float = 0.5, toward: str = "A") -> float:
    """Prior log-odds plus summed log LRs of the DISTINCT items (by item_id) and dependence groups (once per group, its
    strongest member; a group must not mix directions), signed toward `toward`."""
    lo = math.log(prior / (1 - prior)) * (1 if toward == "A" else -1)
    seen, groups = set(), {}
    for it in items:
        if it["item_id"] in seen:
            continue
        seen.add(it["item_id"])
        if it["favours"] == "neutral":
            continue
        g = it.get("dependence_group")
        if g:
            cur = groups.get(g)
            if cur is not None and cur["favours"] != it["favours"]:
                raise ValueError(f"dependence group {g} mixes directions")
            if cur is None or item_lr(it) > item_lr(cur):
                groups[g] = it
            continue
        lo += math.log(item_lr(it)) * (1 if it["favours"] == toward else -1)
    for it in groups.values():
        lo += math.log(item_lr(it)) * (1 if it["favours"] == toward else -1)
    return lo


def _cap(s: str) -> str:
    s = s.strip()
    return s[:1].upper() + s[1:]


def build_scenario(story: dict, truth: str, bank: str, challenge: bool = False) -> dict:
    """One scenario spec (schema v1.0) from a story and a truth. The report always favours F = other(truth)."""
    if truth not in OPTIONS:
        raise ValueError(truth)
    F = other(truth)
    sid = f"{story['story_id']}-{truth}" + ("-challenge" if challenge else "")
    rec_freq = FREQ[RECORD_ACCURACY]
    items = [
        {"item_id": "report", "favours": F, "accuracy": str(HEARSAY_ACCURACY), "dependence_group": None,
         "kind": "hearsay_report",
         "text": REPORT_SENTENCE.format(source=story["report_source"], freq=FREQ[HEARSAY_ACCURACY],
                                        claim=story["claim"][F])},
        {"item_id": "record", "favours": truth, "accuracy": str(RECORD_ACCURACY), "dependence_group": None,
         "kind": "firsthand_record",
         "text": RECORD_SENTENCE.format(source=story["record_source"], freq=rec_freq, fact=story["fact"][truth])},
    ]
    for k, n in enumerate(story["neutral"]):
        items.append({"item_id": f"neutral{k}", "favours": "neutral", "accuracy": str(RECORD_ACCURACY),
                      "dependence_group": None, "kind": "neutral_record",
                      "text": RECORD_SENTENCE.format(source=story["record_source"], freq=rec_freq, fact=n)})
    for k, s in enumerate(story["shared"]):
        items.append({"item_id": f"shared{k}", "favours": "neutral", "accuracy": "none", "dependence_group": None,
                      "kind": "shared_context", "text": _cap(s)})
    if challenge:
        items.append({"item_id": "weak_shared", "favours": F, "accuracy": str(WEAK_ACCURACY), "dependence_group": None,
                      "kind": "shared_weak_report",
                      "text": WEAK_SENTENCE.format(source=story.get("weak_source", "a neighbour"),
                                                   freq=FREQ[WEAK_ACCURACY], claim=story["claim"][F])})
    spec = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": f"mp-{sid}",
        "study": "MissingPiece",
        "bank": bank,
        "story": {"story_id": story["story_id"], "question": story["question"], "options": dict(story["options"]),
                  "report_source": story["report_source"], "record_source": story["record_source"]},
        "hidden_state": truth,
        "prior": 0.5,
        "evidence_model": {
            "type": "mp_hearsay_vs_record_v1",
            "report_option": F,
            "items": items,
            "holdings": holdings_template(challenge),
        },
        "pooled_margin_logodds": POOLED_MARGIN,
        "challenge_set": bool(challenge),
    }
    spec["evidence_model"]["pooled"] = pooled_by_cell(spec)
    spec["evidence_model"]["solvable_verifier_present"] = all(
        spec["evidence_model"]["pooled"][c]["group_toward_truth"] >= POOLED_MARGIN for c in ("UP", "KP"))
    return spec


def holdings_template(challenge: bool = False) -> dict:
    """Which item ids each ROLE holds in each cell (positions and which neutral record goes to whom are drawn per game).
    'N' stands for that holder's own neutral record. The verifier holder is one receiver, chosen per game."""
    shared = ["shared0", "shared1"] + (["weak_shared"] if challenge else [])
    out = {}
    for c in CELLS:
        knowing, present = c[0] == "K", c[1] == "P"
        out[c] = {"speaker": shared + ["report", "record" if knowing else "N"],
                  "verifier_holder": shared + ["record" if present else "N"],
                  "other_receivers": shared + ["N"]}
    return out


def cell_items(spec: dict, cell: str, who: str) -> list[dict]:
    by_id = {it["item_id"]: it for it in spec["evidence_model"]["items"]}
    ids = spec["evidence_model"]["holdings"][cell][who]
    return [by_id[i] for i in ids if i != "N"]


def pooled_by_cell(spec: dict) -> dict:
    """Pooled-evidence benchmark per cell: the whole group (distinct items, shared counted once) and the receivers only."""
    T = spec["hidden_state"]
    out = {}
    for c in CELLS:
        rec = cell_items(spec, c, "verifier_holder") + cell_items(spec, c, "other_receivers")
        grp = cell_items(spec, c, "speaker") + rec
        g, r = pooled_logodds(grp, spec["prior"], T), pooled_logodds(rec, spec["prior"], T)
        out[c] = {"group_toward_truth": round(g, 6), "receivers_toward_truth": round(r, 6),
                  "group_posterior_truth": round(1 / (1 + math.exp(-g)), 6)}
    return out


REQUIRED = ["schema_version", "scenario_id", "study", "bank", "story", "hidden_state", "prior", "evidence_model",
            "pooled_margin_logodds", "challenge_set"]


def validate(spec: dict, schema: dict | None = None) -> list[str]:
    """Problems with a scenario spec (empty = valid): the shared JSON schema v1.0 plus Missing Piece's own checks."""
    p = []
    if schema is not None:
        import jsonschema
        v = jsonschema.Draft202012Validator(schema)
        p += [f"schema: {e.message}" for e in v.iter_errors(spec)]
    p += [f"missing {k}" for k in REQUIRED if k not in spec]
    if p:
        return p
    em = spec["evidence_model"]
    T, F = spec["hidden_state"], em["report_option"]
    if F != other(T):
        p.append("the report must favour the false option")
    by = {it["item_id"]: it for it in em["items"]}
    if by["report"]["favours"] != F or by["record"]["favours"] != T:
        p.append("report/record directions")
    if sum(1 for i in by if i.startswith("neutral")) != 5:
        p.append("need 5 neutral records (speaker + 4 receivers)")
    for c in ("UP", "KP"):
        if em["pooled"][c]["group_toward_truth"] < spec["pooled_margin_logodds"]:
            p.append(f"{c} not solvable at the margin")
    if spec["prior"] != 0.5:
        p.append("prior must be 0.5")
    return p


def scenario_hash(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
