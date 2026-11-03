# S0 report: pinned pipeline and serialisation (CPU part)

**Date:** 2026-11-03.
**Status:** **CPU part passes.** The GPU part (option tokens, stop ids and a live byte-identity probe for multi-turn
Missing Piece prompts on a served model) has not run. It waits for the owner's approval of GPU spend. No model was
called and nothing was paid for.

**Re-run:** `python gates/S0/run_s0.py`. Results are in `artifacts/s0_results.json`; rendered transcripts are in
`artifacts/transcripts/`.

## 1. Pin

| what | value | how checked |
|---|---|---|
| pipeline | sae-ethos-pipeline **v1.2.0** | `git rev-parse v1.2.0^{commit}` in a clone of SAE-Ethos-Calibration gives `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b`; the tag is lightweight (coordination `PIPELINE.md`) |
| installed commit | `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b` | `pip install "sae-ethos-pipeline @ git+…@5ca15f56…"`; `lineup.manifest.check_pin` passes for all five models (`mp.manifest.check_environment`; read from pip's `direct_url.json`) |
| lineup file | sha256 `74327b48de5c741f…` | identity block per model, recorded in `s0_results.json` |
| coordination record | `9c155beb9054a9b639d41d0b92d1dfce11f81ac1` (D1–D30, A1–A27), re-pinned to `3f223e7b7e8e` once MP's entries D31–D38 and A28 were added (branch `claude/festive-ritchie-e5hga4`, pending merge) | `pins.yaml` |
| evidence schema | v1.0, sha256 `cd186ef99b4dfa12…` (a copy in `gates/S1/schema/`) | byte copy of the coordination record's `schema/evidence_schema_v1.0.json` |

Missing Piece builds no model serving. Every run manifest starts with `mp.manifest.header(model, server_start)`. That
header refuses to build without a server-start ID (D14) and refuses to run on any pipeline commit other than the pin.

## 2. Chat templates used for the agreement check

Each template hashes exactly to the model's pinned `chat_template_hash`, using the function in `lineup.identity`.

| family | models | template source | sha256[:16] | pin |
|---|---|---|---|---|
| llama3 | Llama-3.1-8B-Instruct | pipeline fixture (OID-verified mirror, pipeline provenance) | `e10ca381b1ccc5cf` | match |
| gemma2 | Gemma-2-9B-IT | `tokenizer_config.json` of a public mirror (the google repository is gated); accepted only because its hash equals the pin | `ecd6ae513fe103f0` | match |
| gemma3 | Gemma-3-27B-IT | pipeline fixture | `7de1c58e208eda46` | match |
| qwen3_5 | Qwen3.5-9B, Qwen3.5-27B | pipeline fixture | `a4aee8afcf2e0711` | match |

## 3. Template agreement on Missing Piece transcripts

A full game was built for each model on `mp-dev-clinic-nurse-cert-A` in the KP cell. It ran 4 rounds plus the vote, the
exit poll and a conviction probe after every round, on the CPU mock backend. Every distinct context was serialised with
the pipeline's canonical serializer and also rendered by the official template, using Jinja configured the way
transformers configures it. The two renderings were compared as strings, with BOS stripped.

| model | contexts compared | agree | context shapes (user turns) |
|---|---|---|---|
| llama-3.1-8b-it | 55 | **55** | message 1–4, probe 2–5, vote 5, exit poll 6 |
| gemma-2-9b-it | 55 | **55** | same |
| gemma-3-27b-it | 55 | **55** | same |
| qwen3.5-9b | 55 | **55** | same |
| qwen3.5-27b | 55 | **55** | same |

The Missing Piece context is system-free and strictly alternating:
- The opening user turn holds the role-neutral instructions, the question and the agent's own briefing.
- The agent's own earlier messages are assistant turns.
- Other agents' messages and round markers sit in the user turns between them.

This is the conversation class on which all five templates agree. Gemma-2 has no system role, so a system message would
be folded into turn 0 (coordination `DECISIONS.md`, "System messages"). Missing Piece uses none.

## 4. Deviations and open items

- **None from the pin.**
- **Gemma-2 template source.** The google repository is gated, so the template came from a public mirror and was
  accepted only on an exact hash match to the pin. On the box, `modelcfg.template_agreement` re-checks it against the
  tokenizer fetched at the pinned revision.
- **Not yet checked (GPU):**
  - token-level agreement: `apply_to_tokenizer` ids against the template's ids;
  - single-token `A` and `B` after each generation prompt (`lineup.readout.option_token_ids`);
  - stop ids;
  - a repeat probe on a multi-turn Missing Piece vote prompt within one start.

  StPT's S0 box check passed these for its single-turn prompts on all five models (coordination A4). Missing Piece runs
  them on its first approved pod, before any other call. Estimated cost: under one pod-hour.
- **Known pipeline defect (A3).** `pod/serve_lineup.sh` cannot import `lineup`. Missing Piece will start servers with
  the pipeline's `lineup-serve-cmd` console script, as StPT's driver does.

**Stop here.** Next gate: S1, evidence specifications (CPU).
