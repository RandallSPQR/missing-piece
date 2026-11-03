"""Serving modes for Missing Piece runs (owner, 2026-11-03: cost reduction, engineering only).

  strict                 pipeline v1.2.0's serving (batch size 1, prefix caching off). The only mode the pinned
                         pipeline supports. Default.
  throughput             prefix caching on, up to 32 sequences in flight, games run in lockstep cohorts (mp.runner).
  throughput_invariant   as throughput, with vLLM batch-invariant kernels.

The two non-strict modes change pinned serving values, so they need a new pipeline version (proposed: v1.3.0,
proposals/pipeline-v1.3.0/, a logged entry in the coordination record) and they also amend accepted decisions D1 (batch
size 1) and D9 (prefix cache off) for Missing Piece. They are refused here until (a) the pin moves to a pipeline release
with serving modes and (b) the mode has passed its S0-GPU validation for that model (`validated_modes` in pins.yaml).
The same mode serves all four cells of every quad; the mode is recorded in every run manifest."""
from __future__ import annotations

MODES = {
    "strict": {"prefix_caching": False, "max_num_seqs": 1, "batch_invariant": False, "runner": "sequential"},
    "throughput": {"prefix_caching": True, "max_num_seqs": 32, "batch_invariant": False, "runner": "lockstep"},
    "throughput_invariant": {"prefix_caching": True, "max_num_seqs": 32, "batch_invariant": True, "runner": "lockstep"},
}


def _ver(v: str) -> tuple:
    return tuple(int(x) for x in v.split(".")[:3])


def check_mode(mode: str, pipeline_version: str, model: str, pins: dict) -> dict:
    if mode not in MODES:
        raise ValueError(f"unknown serving mode {mode!r}")
    if mode != "strict":
        if _ver(pipeline_version) < (1, 3, 0):
            raise RuntimeError(f"serving mode {mode!r} needs a pipeline release with serving modes (proposed v1.3.0); "
                               f"installed {pipeline_version}. See proposals/pipeline-v1.3.0/.")
        ok = ((pins.get("serving") or {}).get("validated_modes") or {}).get(model, [])
        if mode not in ok:
            raise RuntimeError(f"serving mode {mode!r} has not passed S0-GPU validation for {model} "
                               f"(pins.yaml serving.validated_modes)")
    return {"mode": mode, **MODES[mode]}
