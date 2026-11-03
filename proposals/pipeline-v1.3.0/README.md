# Proposed pipeline release: sae-ethos-pipeline v1.3.0 (serving modes)

**Status:** PROPOSED, not tagged.
- This session has read-only access to RandallSPQR/SAE-Ethos-Calibration. The patch is here for the owner, or the StPT
  session, to apply, tag and publish.
- Logged in the coordination record as P12.

**Name.** v1.3.0, not v1.2.1: v1.2.1 is the restart-drift candidate rejected in A6.

| | |
|---|---|
| base | v1.2.0 = `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b` |
| patch | `0001-v1.3.0-serving-modes.patch` (`git am` on the base); sha256 `3bc04907fe4ee40960916607c166fdc065f12e7479154efc2ecf027d2ab8af9f` |
| files | `lineup.yaml` (serving.modes), `lineup/serve.py` (`--mode`, `mode_flags`, `env(mode)`), `lineup/manifest.py` (`identity_block(name, mode)`), version strings, tests, RELEASE_NOTES |
| tests (CPU) | `pytest pipeline/lineup/tests`: 43 pass, 24 skipped; the same skips as v1.2.0 (tokenizer fixtures) |

**What it does.**
- The default mode `strict` is the v1.2.0 determinism flag set, unchanged. New tests assert that the command and flags
  equal v1.2.0's for all five models.
- Opt-in modes:
  - `throughput`: `--enable-prefix-caching`, `--max-num-seqs 32`, `--enable-prompt-tokens-details`.
  - `throughput_invariant`: as `throughput`, plus `VLLM_BATCH_INVARIANT=1` and `--attention-backend FLASH_ATTN`.
- The identity block records the mode, its effective flags and env, and the batch size.

**After tagging:**
1. Missing Piece re-pins (tag and commit) in `pins.yaml` and logs it.
2. MP S0-GPU runs C1–C3 per model (`gates/S0/S0_GPU_PLAN.md`).
3. Models that pass are entered in `pins.yaml` `serving.validated_modes`; until then `mp.serving.check_mode` refuses
   them.

StPT can stay on v1.2.0, or move to v1.3.0 in `strict` mode with no behavioural change.
