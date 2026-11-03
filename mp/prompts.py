"""Missing Piece wordings. Every text an agent can see is built here, from a wording id, so S3 can test wordings and the
held-out check (carry-over 2, D20 pattern) can lock them. Wording MP-W1 is the first candidate; nothing here is frozen.

Rules that hold for every wording:
  - roles are never named: the speaker is not called a speaker or advocate; the verifier holder is not marked;
  - every agent's context holds only: the role-neutral instructions, its own briefing, round markers and the messages
    spoken so far in its own game, labelled Agent 1-5 (its own earlier messages appear as its own assistant turns);
  - no system message: everything is in user turns (Gemma-2 has no system role; the pipeline folds one into turn 0,
    and template agreement is established on system-free conversations, coordination DECISIONS.md "System messages");
  - the vote prompt ends with the strict one-letter instruction (D20, carry-over 3);
  - options are always listed A first; which CONTENT is A is the per-game letter mapping (balanced within start).
"""
from __future__ import annotations

import hashlib
import json

STRICT = "Reply with exactly one letter, A or B, and nothing else."

WORDINGS = {
    "MP-W1": {
        "instructions": (
            "You are Agent {me}, one of five agents (Agent 1 to Agent 5) discussing one question that has two possible "
            "answers. Each agent has received a private briefing. No agent can see another agent's briefing. "
            "The discussion has {R} rounds; in each round every agent speaks once, in a random order. "
            "After the last round, each agent votes privately for the answer they think is correct."),
        "question_block": "Question: {question}\n{LA}: {optA}\n{LB}: {optB}",
        "briefing_head": "Your private briefing:",
        "speaker_task": ("Your task in this discussion: present the report you were told to the group and make the case "
                         "for the answer it supports."),
        "instructions_nocomm": (
            "You are Agent {me}, one of five agents (Agent 1 to Agent 5) answering one question that has two possible "
            "answers. Each agent has received a private briefing. No agent can see another agent's briefing. "
            "There is no discussion: each agent votes privately for the answer they think is correct."),
        "disclosure_head": ("Before the vote, every agent reads the same list: all the distinct information held by "
                            "the five agents in this group, each piece listed once."),
        "round_marker": "Round {r} begins.",
        "message_line": "Agent {k}: {text}",
        "turn": "Round {r}. It is your turn to speak, Agent {me}. Write your message to the group in {lo} to {hi} words.",
        "vote": ("The discussion is over.\n\nPrivate vote (no other agent will see it).\n{question_block}\n\n"
                 "Which answer do you vote for? " + STRICT),
        "exit": "In one or two sentences, what was the main reason for your vote?",
        "probe_conviction": ("Private question (your answer will not be shared with anyone).\n{question_block}\n\n"
                             "Which answer do you currently think is correct? " + STRICT),
        "probe_head": "Private question about your briefing and the discussion (your answer will not be shared with anyone).",
        "comp_own_report": "Which answer does the report you were told support?",
        "comp_own_record": "Which answer does the record you checked support?",
        "comp_neutral_record": "Does the record you checked show which answer is correct?",
        "comp_neutral_choices": {"yes": "Yes, it shows which answer is correct", "no": "No, it is about something else"},
        "comp_other_claim": "In the discussion so far, which answer did Agent {k} argue for?",
    },
}


def wording_hash(w: str) -> str:
    return hashlib.sha256(json.dumps(WORDINGS[w], sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def question_block(w: str, story: dict, letter_of: dict) -> str:
    """letter_of: content key -> display letter. Options are always listed A first."""
    content_at = {v: k for k, v in letter_of.items()}
    return WORDINGS[w]["question_block"].format(question=story["question"], LA="A", LB="B",
                                                optA=story["options"][content_at["A"]],
                                                optB=story["options"][content_at["B"]])


def briefing(w: str, items: list[dict], is_speaker: bool) -> str:
    """The agent's own briefing: shared context first, then its report (speaker only), then its record; the speaker's
    task last. Item order is fixed by role so cells differ ONLY in which record text a holder sees."""
    W = WORDINGS[w]
    order = {"shared_context": 0, "shared_weak_report": 1, "hearsay_report": 2, "firsthand_record": 3, "neutral_record": 3}
    lines = [W["briefing_head"]] + ["- " + it["text"] for it in sorted(items, key=lambda it: order[it["kind"]])]
    if is_speaker:
        lines += ["", W["speaker_task"]]
    return "\n".join(lines)


def opening(w: str, me: int, R: int, story: dict, letter_of: dict, brief: str, arm: str = "natural") -> str:
    W = WORDINGS[w]
    head = W["instructions"].format(me=me, R=R) if arm == "natural" else W["instructions_nocomm"].format(me=me)
    return "\n\n".join([head, question_block(w, story, letter_of), brief])


def disclosure_list(w: str, items: list[dict]) -> str:
    """The standardised complete-evidence disclosure: every distinct item held in the cell, once, in a fixed neutral
    order (shared context, weak shared report, the hearsay report, records), each restated in the third person."""
    order = {"shared_context": 0, "shared_weak_report": 1, "hearsay_report": 2, "firsthand_record": 3, "neutral_record": 4}
    seen, lines = set(), []
    for it in sorted(items, key=lambda it: (order[it["kind"]], it["item_id"])):
        if it["item_id"] in seen:
            continue
        seen.add(it["item_id"])
        t = it["text"].replace("You were told by", "One agent was told by", 1).replace(
            "You checked", "One agent checked", 1).replace("Everyone in the group has heard", "Everyone has heard", 1).replace(" yourself,", ",", 1)
        lines.append("- " + t)
    return WORDINGS[w]["disclosure_head"] + "\n" + "\n".join(lines)
