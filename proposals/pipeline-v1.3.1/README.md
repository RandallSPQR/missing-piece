# Proposed pipeline release: sae-ethos-pipeline v1.3.1 (fix to v1.3.0's serving modes)

**Status:** PROPOSED, not tagged. This session can only read the pipeline repository.

**What broke in v1.3.0.** A mode's flag replacements were applied only to the lineup's determinism list. The Qwen3.5
profiles set `--max-num-seqs 1 --no-enable-prefix-caching` in their own `serve.extra_args`, and the command builder
never repeats a flag a profile sets. So under `throughput` and `throughput_invariant` the Qwen pair ran with one
sequence in flight. Prefix caching came on only because the mode's `--enable-prefix-caching` came after the profile's
`--no-` flag on the command line.
- Found in MP S0-GPU: the Qwen3.5-9B vLLM log shows `Running: 1 reqs, Waiting: 27 reqs`, and the pod's
  `serve_cmd_throughput.txt` holds both `--max-num-seqs 1` and `--no-enable-prefix-caching`.
- Llama, Gemma-2 and Gemma-3 were served as intended. Their profiles set at most `--no-enable-prefix-caching`, which
  the mode's later flag overrides.
- Strict mode was never affected.

**Fix.** A non-strict mode also rewrites the flags it replaces inside the profile's args, so each flag appears once with
the mode's value.

| | |
|---|---|
| base | v1.3.0 = `37031bcd0d33b6dbd2c6f6573127714367c306fe` |
| patch | `0001-v1.3.1-mode-flags-in-profile-args.patch`; sha256 `18ffa3d41bc7e64ee52157c61c3cd6ea3732b3ff42c30844b697d508ce168003` |
| tests (CPU) | 58 pass, 24 skipped. New: the FULL command for every model under every mode has each flag once, prefix caching on and `--max-num-seqs 32`; the strict command is unchanged |
| link check | v1.3.1 strict is byte-identical to v1.2.0 for all five models (`gates/S0/link_check/v1.3.1-strict.json`) |
