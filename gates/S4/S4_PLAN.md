# S4 plan: pilot on the development bank

**Status:** the CPU half of the probe-isolation check **passes** (`results/isolation_cpu.json`). The pilot itself is
**not run** (GPU, awaiting approval).

## CPU probe isolation: PASS

`python gates/S4/isolation_cpu.py`:
- **Scope:** every development scenario (32) × all four cells × two serializers (gemma2, qwen3_5) = 256 games;
  7,682 live calls compared.
- **Byte-identity:** every game's live calls (serialised prompt sha256 and output, in order) are byte-identical with
  and without the private conviction probe after every round (5,120 probes run).
- **Negative control:** in every game, a leaky probe (one that writes its trace into the event list) **was detected**.

The engine rebuilds each live context from the game's event list. Probes run on fresh copies and write only to a probe
log that no live context reads.

## Pilot (GPU)

Development bank only. All four cells of each quad run within one server start, and F's display letter is balanced
within each start.

| question | design | pre-stated rule |
|---|---|---|
| Rounds R | 4 (brief's start); pilot also records support after rounds 2 and 3 through the branched conviction probe | R = 4 stands if mean receiver conviction changes by < 0.02 between rounds 3 and 4, pooled over models (95% CI inside ±0.04); otherwise R is brought to the owner. R is never chosen on a knowledge contrast |
| Message band | 60–120 words; out-of-band messages are counted, never regenerated | the band stands if ≥ 90% of messages fall inside it for every model; otherwise the instruction or the band is revised, and the revision is logged before S6 |
| Probe isolation (GPU half) | `mp.isolation.check` on 2 quads per model, in one start each | byte-identical live calls with and without probes; leaky control detected |
| Disclosure mechanics | standardised complete-evidence disclosure arm: before the vote, every agent reads a fixed, neutral list of all distinct items held in its cell | runs end to end; comprehension of the list ≥ 0.90 (one branched check per agent) |
| No-communication control | each agent votes on its own briefing, without talk | runs end to end |
| Invalid votes | strict one-letter instruction; 3 seeded retries | the invalid rate is reported by cell; the non-A/B mass is recorded |
| Variance components for S6 | between-story, between-scenario and within-quad (game) variance of the knowledge contrast, per model | **point estimates of the knowledge and interaction contrasts are sealed** (written once, sha256 recorded in the coordination record's `SEALED.md`, opened only at the owner's request), as StPT D27 |

Pilot size (proposed):
- 6 development stories × 2 truths × 1 replicate × 4 cells = 48 games per model, 240 games in total.
- About 40 GPU minutes for the small models and about 2 h for each 27B model, about 5.5 pod-hours, about $14.
- Pilot quads are never reused in confirmatory work.

## Sampling settings (proposed; not in the brief)

- **Discussion messages:** temperature 0.7, top-p 0.95, seeded per call; max 320 tokens.
- **Votes:** temperature 0.6, top-p 0.9 (brief), seeded; max 4 tokens.
- **Exit polls:** as messages, max 120 tokens.
- Seeds are shared across the four cells of a quad (common random numbers), so cells differ only through the briefings.
