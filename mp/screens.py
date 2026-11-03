"""Anonymity screen: self-identification in agent text (model names, vendors, model-family words). Matches are counted
by cell and adjudicated blind (a grader sees the matched span and its message, never the cell or the model). The term
list follows the Self-ID Mask screens' categories (model / vendor / generic AI self-reference); it is fixed before any
model call and a change to it is a logged amendment."""
from __future__ import annotations

import re

TERMS = {
    "model_name": r"\b(llama|gemma|qwen|gpt|chatgpt|claude|mistral|gemini|bard)\b",
    "vendor": r"\b(meta ai|meta|google|deepmind|alibaba|openai|anthropic)\b",
    "ai_self_reference": r"\b(as an ai|as a language model|language model|large language model|i am an ai|i'm an ai|ai assistant)\b",
}
_RX = {k: re.compile(v, re.I) for k, v in TERMS.items()}


def self_id(messages: list[dict]) -> list[dict]:
    hits = []
    for i, m in enumerate(messages):
        t = m.get("text", "")
        for cat, rx in _RX.items():
            for mm in rx.finditer(t):
                hits.append({"index": i, "label": m.get("label"), "category": cat, "span": mm.group(0),
                             "context": t[max(0, mm.start() - 60): mm.end() + 60]})
    return hits
