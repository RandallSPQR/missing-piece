# Missing Piece story format (gate S1)

A story is the reusable text of one scenario family. `gates/S1/make_banks.py` turns each story into two scenario specs
(truth A and truth B; the false report always argues for the option that is NOT the truth), in evidence schema v1.0.
Stories are written **before any model sees them**. Evidence strength is fixed by the rendered sentences below (stated
source accuracies in plain frequencies), never by the wording of the content.

## Rendered sentences (fixed by the generator, `mp/evidence.py`, which is authoritative; writers supply only the slot text)

| item | who holds it | sentence |
|---|---|---|
| report (hearsay) | speaker, every cell | `You were told by {report_source}, who is right about matters like this 3 times out of 4, that {claim[F]}.` |
| record (verifier) | knowing speaker; one receiver in verifier-present cells | `You checked {record_source} yourself, which is right about matters like this 49 times out of 50. It shows that {fact[T]}.` |
| neutral record | uninformed speaker; receivers without the verifier | `You checked {record_source} yourself, which is right about matters like this 49 times out of 50. It shows that {neutral[k]}.` |
| shared context | all five agents | each `shared` sentence as written |

T = the true option, F = the other option.

## YAML fields (one list item per story)

```yaml
- story_id: nurse-cert              # lowercase, hyphens, unique across BOTH banks
  question: "Is Dana Reyes's nursing certification currently valid?"
  options: {A: "Yes, it is currently valid", B: "No, it has lapsed"}
  report_source: "a colleague from the hospital's front office"
  claim: {A: "Dana Reyes's certification was renewed this spring",          # a clause after "that"; favours A
          B: "Dana Reyes's certification lapsed in January"}                # favours B
  record_source: "the state nursing registry"
  fact: {A: "Dana Reyes's certification is current and was renewed in March",   # decisive for A
         B: "Dana Reyes's certification lapsed in January and was not renewed"} # decisive for B
  neutral:                           # exactly 5; same source; irrelevant to the question
    - "the licensing office moved to a new building in March"
    - "the registry added an online renewal form last year"
    - "the registry lists four hundred nurses in the county"
    - "the registry's phone line is open on weekday mornings"
    - "the registry updated its address format in the autumn"
  shared:                            # exactly 2; background every agent holds; no evidence either way
    - "The hospital is filling a night-shift nursing post this month."
    - "Dana Reyes applied for the post two weeks ago."
```

## Rules (the S2 lint checks every one)

1. Fictional people, places and organisations; nothing answerable from world knowledge; low stakes and harmless (no
   medicine dosing, weapons, crime, politics, religion, health advice, or real brands).
2. `options`: each at most 8 words; neither is the obvious default; together exhaustive and exclusive.
3. `claim[A]` / `claim[B]`: clauses that follow "that"; each clearly supports its option alone; within 2 words of each
   other in length. They are HEARSAY (something someone said), never a record.
4. `fact[A]` / `fact[B]`: clauses after "It shows that"; each settles the question for its option; within 2 words of each
   other; 8 to 14 words.
5. `neutral` (5): same `record_source`, 8 to 14 words, each within 2 words of BOTH facts' lengths; plausible things that
   source would show; must not bear on the question in either direction, must not mention the options' content, and
   must not contradict either claim.
6. `shared` (2): full sentences; background only; must not favour either option.
7. The question names the decision; the options are answers to it. No item mentions "Agent", "speaker", "verifier",
   "advocate", "lie", "truth", "false" or "true".
8. Use plain words. British or American spelling is fine but be consistent within a story.
