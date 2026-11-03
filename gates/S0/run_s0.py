"""Gate S0 (CPU): pinned pipeline and serialisation.

1. Pin: the installed sae-ethos-pipeline is v1.2.0 at commit 5ca15f56 (lineup.manifest.check_pin via
   mp.manifest.check_environment) for every model; the identity block of each model is recorded.
2. Templates: every chat template used for the agreement check hashes to the model's pinned chat_template_hash.
3. Rendered multi-turn transcripts per model: a full Missing Piece game (4 rounds, vote, exit poll, a conviction probe
   branch) is built on a development scenario with the CPU mock backend; every distinct context shape is serialised with
   the PIPELINE's canonical serializer and written to artifacts/transcripts/.
4. Template agreement: each serialised context is compared, as a string, with the model's official chat template
   rendered by Jinja exactly as transformers renders it (sandboxed, trim_blocks, lstrip_blocks), BOS stripped.
   Agreement is required on every Missing Piece context shape (system-free, strictly alternating, multi-turn).
5. Option tokens and stop handling are box checks (tokenizers): StPT S0 established them on this pipeline for all five
   models (coordination PIPELINE.md, box identity check PASSED 2026-10-31); MP re-runs them on its first approved pod.

Writes artifacts/s0_results.json. No model is called; nothing is paid for."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

import jinja2  # noqa: E402
import jinja2.ext  # noqa: E402
from jinja2.sandbox import ImmutableSandboxedEnvironment  # noqa: E402

from mp import manifest as mf  # noqa: E402
from mp.assign import make_plan  # noqa: E402
from mp.backend import MockBackend  # noqa: E402
from mp.protocol import Game, Settings  # noqa: E402

TEMPLATES = {"llama3": "llama3.1-8b-instruct_chat_template.jinja", "gemma2": "gemma2_chat_template.jinja",
             "gemma3": "gemma3_chat_template.jinja", "qwen3_5": "qwen3.5_chat_template.jinja"}
BOS = {"llama3": "<|begin_of_text|>", "gemma2": "<bos>", "gemma3": "<bos>", "qwen3_5": ""}
KWARGS = {"qwen3_5": {"enable_thinking": False}}
SCENARIO = ROOT / "gates/S1/banks/development/mp-dev-clinic-nurse-cert-A.json"


def render_template(src: str, messages, family: str) -> str:
    def raise_exception(msg):
        raise jinja2.exceptions.TemplateError(msg)

    env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=[jinja2.ext.loopcontrols])
    env.filters["tojson"] = lambda x, indent=None, ensure_ascii=False: json.dumps(x, indent=indent, ensure_ascii=ensure_ascii)
    env.globals["raise_exception"] = raise_exception
    t = env.from_string(src)
    out = t.render(messages=messages, add_generation_prompt=True, bos_token=BOS[family],
                   eos_token="", **KWARGS.get(family, {}))
    b = BOS[family]
    return out[len(b):] if b and out.startswith(b) else out


class Capture(MockBackend):
    """Mock backend that also keeps every distinct context it is asked to serialise (live and probe)."""

    def __init__(self, model):
        super().__init__(model)
        self.seen = []

    def generate(self, messages, **kw):
        self.seen.append(("live", [dict(m) for m in messages]))
        return super().generate(messages, **kw)

    def readout(self, messages):
        self.seen.append(("readout", [dict(m) for m in messages]))
        return super().readout(messages)


def main():
    pins = mf.pins()
    spec = json.loads(SCENARIO.read_text())
    res = {"pins": {"pipeline": pins["pipeline"], "coordination": pins["coordination"]}, "models": {}}
    tdir = HERE / "artifacts" / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    all_ok = True
    for model in pins["models"]:
        block = mf.check_environment(model)          # raises if the installed pipeline is not the pinned commit
        fam = block["model"]["family"]
        tsrc = (HERE / "artifacts" / "templates" / TEMPLATES[fam]).read_text()
        thash = hashlib.sha256(tsrc.encode()).hexdigest()[:16]
        be = Capture(model)
        plan = make_plan(spec, model, 0, rounds=4, tag="s0")
        g = Game(spec, plan, "KP", be, Settings())
        g.run(probes=True)
        shapes, agree, examples = {}, [], {}
        for kind, msgs in be.seen:
            n_user = sum(m["role"] == "user" for m in msgs)
            last = msgs[-1]["content"]
            shape = ("vote" if "Private vote" in last and msgs[-1]["role"] == "user" and "main reason" not in last else
                     "exit" if "main reason" in last else
                     "probe" if "Private question" in last else "message") + f"_u{n_user}"
            ours = be.serialize(msgs)
            theirs = render_template(tsrc, msgs, fam)
            ok = ours == theirs
            agree.append(ok)
            shapes.setdefault(shape, 0)
            shapes[shape] += 1
            if shape not in examples:
                examples[shape] = ours
                if not ok:
                    examples[shape + "_TEMPLATE"] = theirs
        for shape, text in examples.items():
            (tdir / f"{model}__{shape}.txt").write_text(text)
        m_ok = all(agree) and thash == block["model"]["chat_template_hash"]
        all_ok &= m_ok
        res["models"][model] = {
            "pipeline_commit": block["pipeline"]["commit"], "pipeline_tag_requested": block["pipeline"]["tag"],
            "pipeline_how": block["pipeline"]["how"], "lineup_sha256": block["lineup"]["sha256"],
            "family": fam, "serializer_sha256": block["serializer"]["sha256"],
            "chat_template_hash_pinned": block["model"]["chat_template_hash"], "chat_template_hash_used": thash,
            "contexts_checked": len(agree), "contexts_agree": sum(agree), "shapes": shapes,
            "max_user_turns": max(int(s.split("_u")[1]) for s in shapes), "pass": m_ok,
        }
        print(model, res["models"][model]["contexts_agree"], "/", len(agree), "agree; template hash ok:",
              thash == block["model"]["chat_template_hash"])
    res["pass"] = all_ok
    (HERE / "artifacts" / "s0_results.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print("S0 CPU pass:", all_ok)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
