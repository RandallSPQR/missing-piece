"""Dump everything a pipeline install contributes to serving and serialisation, for the v1.2.0 vs v1.3.0-strict link
check: per model the exact vLLM argv and env (strict mode), the lineup model entry, the profile sha256, the
serializer source sha256, and the sha256 of lineup/readout.py. Run once under each install; compare the two JSONs."""
import hashlib
import inspect
import json
import sys

import sae_ethos_pipeline
import lineup
import model_io
from lineup import readout, serve

out = {"version": sae_ethos_pipeline.__version__, "readout_sha256": hashlib.sha256(inspect.getsource(readout).encode()).hexdigest(),
       "models": {}}
for name, e in lineup.models().items():
    ser = model_io.get(e["family"])
    out["models"][name] = {
        "argv": serve.vllm_argv(name, python="PY"), "env": serve.env(),
        "entry": e, "profile_sha256": hashlib.sha256((lineup.CONFIG / e["profile"]).read_bytes()).hexdigest(),
        "serializer_sha256": hashlib.sha256(open(ser.__file__, "rb").read()).hexdigest(),
        "serving_pins": lineup.lineup()["serving"]["pins"], "readout_cfg": lineup.lineup()["serving"]["readout"]}
json.dump(out, sys.stdout, indent=1, sort_keys=True)
