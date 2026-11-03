# S3 plan: comprehension on the development bank (branched); responsiveness

**Status:** planned and built. **Not run** (GPU, awaiting approval). Nothing here touches the confirmatory bank.

## Comprehension

- **Builder:** `mp.singles.comprehension(specs, model, seed_tag)`.
- **Context for each probe:** the agent's real Missing Piece context after a scripted first message by the speaker. The
  speaker restates the report and names the answer it supports. That message is the only one so far.
- **Branching:** the question is asked on a forked branch (a fresh copy of the context plus one user turn) and is never
  written back.
- **Readout:** exact P(A) and P(B). An item is correct when the key's probability is the larger.

| type | asked of | question | key |
|---|---|---|---|
| own_report | the speaker | "Which answer does the report you were told support?" | F's letter |
| own_record | holders of the contradicting record (knowing speaker; verifier holder in P cells) | "Which answer does the record you checked support?" | T's letter |
| neutral_record | holders of a neutral record | "Does the record you checked show which answer is correct?" (Yes / No, it is about something else; letters seeded) | "No" |
| other_claim | receivers | "In the discussion so far, which answer did Agent {s} argue for?" | F's letter |

On the development bank this gives 1,280 items per model (32 specs × 4 cells × 5 agents, 1–2 questions each).

**Rule, fixed before any call:**
- MP-W1 passes for a model if every type reaches **≥ 0.90** on round 1.
- Non-A/B mass is reported per type.

**Held-out check (carry-over 2, D20 pattern):**
- A fresh comprehension set on the development bank, `seed_tag="S3-heldout"`, which redraws labels, holders, letters and
  choice order.
- It runs MP-W1 and up to three variant wordings, written after round 1 and before any held-out call. The variants keep
  the structure but change the phrasing and the label text; the strict one-letter instruction is kept.
- A wording is valid for a model if all four types reach ≥ 0.90 on the held-out set.
- No wording is frozen until this check has run.
- If no single wording passes for every model, each model is read in its own valid wording set (as StPT D21). The
  pooled confirmatory test uses the primary wording only for the models valid in it.
- **Expected fragility:** the 9B models (carry-over 2). StPT saw Qwen3.5-9B own-report at 0.867 under W1 and Gemma-2
  own-vote at 0.683 under W2.

**Llama-3.1-8B (carry-over 4)** is judged by Missing Piece's own gates (S3 here, S4 mechanics), not by StPT's S6. If it
fails a Missing Piece gate under a pre-stated rule, that is a gate outcome. All its runs are kept and it is reported as
a secondary comparison model.

## Responsiveness to item wording (brief: measured separately from design strength)

- **Builder:** `mp.singles.responsiveness`.
- **Requests:** single-agent readouts with the question plus one item alone, for both letter mappings. Items: hearsay
  3/4, record 49/50, a neutral record, and nothing.
- **Reported per model:**
  - P(the option the item favours), against the design posteriors 0.75 and 0.98;
  - the shift a neutral record causes relative to nothing (the "absence" reading, `gates/S1/CONVENTIONS.md`).
- Never used to define truth or to choose scenarios.

## Cost, if approved

- Per model: about 1,280 comprehension readouts for round 1 and about 2,600 for the held-out set (four wordings ×
  ~650), plus 256 responsiveness readouts.
- Contexts are short: one opening turn and one message.
- About 0.5 pod-hours for all five models, about $1–2.
