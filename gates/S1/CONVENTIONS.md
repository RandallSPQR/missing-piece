# Missing Piece evidence conventions (S1): PROPOSED, awaiting the owner

The brief lists "pooled-evidence margin and the likelihood-ratio conventions for hearsay and records" and "sizes of the
development and confirmatory banks" as decisions still required. The values below are proposals. Both banks are built
on them so that S2–S5 can run. Changing one before the freeze is a prospective amendment in the coordination record.

| convention | proposal | why |
|---|---|---|
| Schema | shared evidence schema **v1.0**, unchanged. Missing Piece fields (`report_option`, per-cell `holdings`, per-cell `pooled`, item `text` and `kind`) sit under `evidence_model` and `story` | carry-over 5; coordination `PROTOCOL_SPEC.md` |
| Source accuracy | stated in plain frequencies inside the item's own sentence; designed LR = a/(1 − a) toward the option the item favours | carry-over 5; the same rule as StPT, so the LR follows from the text alone |
| Hearsay report | "You were told by {source}, who is right about matters like this **3 times out of 4**, that {claim}." **LR 3**, favours the false option F. The text is the same, word for word, in all four cells | the same hearsay strength as StPT's middle level. Taken alone it is moderate evidence (Bayes posterior 0.75), so receivers have reason to support the report and room to move |
| Firsthand record | "You checked {source} yourself, which is right about matters like this **49 times out of 50**. It shows that {fact}." **LR 49**, favours the truth T | "decisive" (brief). With the report it gives pooled log-odds ln 49 − ln 3 = **2.79** toward T (posterior 0.94) |
| Neutral record | the same sentence frame and source as the record, with a fact irrelevant to the question; **LR 1**. Matched to the record within ±2 words (lint L2–L4) | brief: matched in format and length |
| Shared context | two background sentences held by all five agents; LR 1 | gives receivers something to discuss; no evidence either way |
| Prior | 0.5; options balanced by the S2 prior check | brief |
| Dependence | one item_id is one item however many agents hold it. The knowing speaker and the verifier holder hold the **same** record, counted once (KP pooled = UP pooled) | brief |
| Pooled benchmark | prior log-odds plus the summed log LRs of the distinct items held by the group, toward T. **UA −1.10; UP, KA, KP +2.79.** Receivers-only: UA and KA 0; UP and KP +3.89 | computed in every spec (`evidence_model.pooled`) |
| Solvability margin | verifier-present cells (UP, KP) must reach pooled log-odds ≥ **2.2** toward T (posterior ≥ 0.90). All 84 specs reach 2.79 | brief: a prespecified margin for verifier-present cells. In unchallenged cells no receiver can detect the falsity; the outcome there is support, not accuracy |
| Conditional challenge set | development only: 4 stories × 2 truths add a shared weak report for F (3/5, LR 1.5) held by all five; labelled `challenge_set: true`; UP/KP pooled 2.39 ≥ 2.2 | brief: label selected minority-correct profiles. Never in the confirmatory bank; never pooled with representative results |
| Truth balance | each story yields a truth-A and a truth-B scenario; the report always argues for the other option | content balance within story |
| Display letters | which content is shown as letter A is drawn per quad; F's letter is balanced within every server start (seeded permuted blocks) | D20 item 4 |
| Bank sizes | development: 12 stories → 24 specs + 8 challenge variants = **32**. Confirmatory: **26 stories → 52 specs** (≥ 24 stories, carry-over 6). Stories, option texts and sources are disjoint across banks | S6 sizes the run in stories; if a tier needs more stories than the bank holds, the bank is expanded before any confirmatory call, using the same generator and rules |

## Known design facts (documented, not hidden)

- **The knowing speaker holds one decisive fact that the uninformed speaker does not** (brief). The uninformed
  speaker's matched item is a neutral record of the same format and length.
- **Neutral records are firsthand records that show something irrelevant.** A model could read "I checked the record
  and it did not show X" as weak evidence against X. S3/S5 measure this as responsiveness: a neutral record alone,
  compared with no information.
  - If the measured shift is not negligible, it is reported. It is the same in every cell for the receivers, so it
    cannot create a knowledge effect.
  - For the speaker it differs by cell only in the way the brief already accepts (record vs neutral record).
- **Option A of each story is the "yes / done / valid" answer in most stories.** Truth is balanced within story, and the
  display letter is randomised per quad and balanced within start. A content (yes/no) bias therefore cancels within a
  story and cannot touch the within-quad knowledge contrast. The S2 prior check measures it.
