"""Run a GPU-pending single-agent gate for ONE model against a running lineup vLLM server (pipeline v1.2.0 serving
stack, started with the pipeline's `lineup-serve-cmd`). Use only on a pod the owner has approved.

  python gates/run_gpu.py GATE MODEL --bank development --pod POD --start-index 0 --started-at ISO \
      --tokenizer PATH [--base-url http://localhost:8000/v1] [--seed-tag S3-round1]

GATE: prior | refusal | comprehension | responsiveness | solo
Writes gates/<gate dir>/results/<gate>__<model>__<start>.jsonl, the first line being the run manifest header (pins,
pipeline identity, server-start ID). Refuses to run if the installed pipeline is not the pinned commit."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mp import manifest as mf  # noqa: E402
from mp import singles  # noqa: E402
from mp.backend import VLLMBackend  # noqa: E402

DIRS = {"prior": "S2", "refusal": "S2", "comprehension": "S3", "responsiveness": "S3", "solo": "S3"}


def run(args, backend=None):
    specs = [json.loads(p.read_text()) for p in sorted((ROOT / "gates/S1/banks" / args.bank).glob("*.json"))]
    start = mf.server_start_id(args.pod, args.start_index, args.started_at)
    head = mf.header(args.model, start, require_pipeline=backend is None)
    if backend is None:
        from transformers import AutoTokenizer
        backend = VLLMBackend(args.model, AutoTokenizer.from_pretrained(args.tokenizer), base_url=args.base_url)
    build = {"prior": singles.prior_check, "refusal": singles.refusal_screen, "responsiveness": singles.responsiveness,
             "solo": singles.solo_pooled,
             "comprehension": lambda s, m: singles.comprehension(s, m, seed_tag=args.seed_tag)}[args.gate]
    reqs = build(specs, args.model)
    out = ROOT / "gates" / DIRS[args.gate] / "results" / f"{args.gate}__{args.model}__{start['id'].replace('/', '_')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        f.write(json.dumps({"manifest": head, "gate": args.gate, "bank": args.bank, "n_requests": len(reqs),
                            "seed_tag": args.seed_tag}) + "\n")
        for r in reqs:
            t = time.time()
            if r.get("kind") == "generate":
                res = backend.generate(r["messages"], seed=r["seed"], max_tokens=320, temperature=0.7, top_p=0.95)
            else:
                res = backend.readout(r["messages"])
            f.write(json.dumps({"id": r["id"], "key": r.get("key"), "meta": r.get("meta"),
                                "prompt_sha256": backend.prompt_sha256(r["messages"]), "result": res,
                                "seconds": round(time.time() - t, 3)}, default=str) + "\n")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for a in ("gate", "model"):
        ap.add_argument(a)
    ap.add_argument("--bank", default="development")
    ap.add_argument("--pod", required=True)
    ap.add_argument("--start-index", type=int, required=True)
    ap.add_argument("--started-at", required=True)
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--seed-tag", default="S3-round1")
    print(run(ap.parse_args()))
