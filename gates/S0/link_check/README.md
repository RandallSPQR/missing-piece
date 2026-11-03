# Link check: pipeline v1.3.0 (strict) against v1.2.0 (owner, 2026-11-03; optional)

Purpose: confirm that v1.3.0's default `strict` mode serves exactly as v1.2.0. StPT stays pinned to v1.2.0 (D41), and
the matched bridge must run both arms on one pipeline version and serving mode.

## CPU part: PASS (2026-11-03)

`dump_serving.py` was run under two installs, and the two outputs were compared field by field (`cpu_link_check.json`):
- v1.2.0, installed by commit `5ca15f56` (`v1.2.0.json`);
- v1.3.0 as proposed, the `proposals/pipeline-v1.3.0` patch on `5ca15f56` (`v1.3.0-strict.json`).

| per model (all five) | identical? |
|---|---|
| vLLM argv built by `lineup-serve-cmd` (strict) | yes |
| server environment | yes |
| lineup entry (revision, weight_hash, chat_template_hash, family, …) | yes |
| profile sha256 | yes |
| serializer source sha256 | yes |
| serving pins; readout configuration | yes |
| `lineup/readout.py` source | yes |

The vLLM server is launched from that argv and env, in the same serving venv (vLLM 0.19.1 and its pins). It runs no
pipeline code. **A v1.3.0-strict server is therefore the same program, with the same flags, as a v1.2.0 server.**
Client-side serialisation and readout code are byte-identical too.

**Tagged release (2026-11-03).** The owner tagged v1.3.0 at `37031bcd0d33b6dbd2c6f6573127714367c306fe`. Its parent is
`5ca15f56` (v1.2.0), and its tree is identical to the proposal commit. Re-run against the installed tag, the dump is
identical to v1.2.0's for every field and model, and identical to the proposal's (`v1.3.0-tag.json`;
`cpu_link_check.json` → `installed_tag_check`).

## GPU part (optional; not run; runs with S0-GPU)

The check runs StPT's S0 probes (`gates/S0/gpu/box_identity.sh` in the StPT repository: 8 identical readouts on each of
three prompts, plus the exact-fallback check) under a server launched by v1.3.0 `lineup-serve-cmd NAME` (strict).

**Expected result, and the rule.** Bit-identity with v1.2.0 can only be expected within a server start. StPT's S0
measured that a restart alone moves 4 of 5 models by 1–2 bf16 steps (Gemma-2-9B is identical), and S4 found starts fall
into a few discrete numerical states (A16). So, per model, alternate starts in one pod: v1.2.0, v1.3.0, v1.2.0,
v1.3.0. PASS if:
1. within each start, the 8 repeats are bit-identical (both versions);
2. Gemma-2-9B is bit-identical across all four starts;
3. for the other models, every v1.3.0 readout equals a numerical state observed in a v1.2.0 start, or differs from one
   by no more than the largest v1.2.0-to-v1.2.0 restart difference seen in this pod;
4. the box shows the same argv and env from both versions (the CPU comparison above, repeated on the pod).

Cost: about 1 pod-hour for five models (two starts per version).
