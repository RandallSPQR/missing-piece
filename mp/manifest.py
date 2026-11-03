"""The header every Missing Piece run manifest starts with: the pins (pipeline tag + commit, coordination-record commit,
evidence-schema version, brief revision), this repository's commit, the server-start ID (D14) and, for a model call, the
pipeline's identity block. check_environment() refuses a run whose installed pipeline is not the pinned commit."""
from __future__ import annotations

import hashlib
import subprocess
import time

import yaml

from mp import ROOT

PINS_FILE = ROOT / "pins.yaml"


def pins() -> dict:
    return yaml.safe_load(PINS_FILE.read_text())


def mp_source() -> dict:
    def git(*a):
        return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD") or None, "dirty": bool(git("status", "--porcelain"))}


def server_start_id(pod_id: str, start_index: int, started_at: str) -> dict:
    """D14 / carry-over 1: logprobs are bit-identical within one vLLM server start but can move by 1-2 bf16 steps between
    starts. Every manifest records the start; the four cells of a scenario replicate run within one start; the start
    is a blocking factor in every analysis (mandatory for Missing Piece since D22)."""
    if not pod_id or start_index is None or not started_at:
        raise ValueError("a server-start ID needs pod_id, start_index and started_at")
    return {"id": f"{pod_id}/start{int(start_index)}/{started_at}", "pod": pod_id, "index": int(start_index),
            "started_at": started_at}


def header(model: str | None = None, server_start: dict | None = None, require_pipeline: bool = True,
           serving_mode: str = "strict") -> dict:
    """Run-manifest header. A header for a model call must carry the server-start ID, the pipeline identity block and
    the serving mode (mp.serving; the same mode for all four cells of every quad)."""
    if model is not None and not (server_start and server_start.get("id")):
        raise ValueError("a run manifest for a model call must record the server-start ID (D14): pass server_start")
    p = pins()
    h = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "missing_piece": mp_source(), "pins": p,
         "pins_sha256": hashlib.sha256(PINS_FILE.read_bytes()).hexdigest(),
         "pipeline_pin": {"tag": p["pipeline"]["tag"], "commit": p["pipeline"]["commit"]}}
    if server_start is not None:
        h["server_start"] = server_start
    if model is not None and require_pipeline:
        h["pipeline_identity"] = check_environment(model, serving_mode)
    h["serving"] = {"mode": serving_mode}
    if model is not None:
        from mp.serving import MODES
        h["serving"].update(MODES[serving_mode])
    return h


def check_environment(model: str, serving_mode: str = "strict") -> dict:
    """The installed pipeline must be the pinned commit, its lineup must name `model`, and the serving mode must be one
    that pipeline supports and that has passed S0-GPU validation for the model (mp.serving.check_mode)."""
    import sae_ethos_pipeline  # noqa: F401
    from lineup import manifest as lm
    from mp.serving import check_mode
    p = pins()["pipeline"]
    check_mode(serving_mode, sae_ethos_pipeline.__version__, model, pins())
    block = lm.identity_block(model) if serving_mode == "strict" else lm.identity_block(model, mode=serving_mode)
    lm.check_pin(block, p["tag"], p["commit"])
    if model not in pins()["models"]:
        raise RuntimeError(f"{model} is not in Missing Piece's model list")
    return block
