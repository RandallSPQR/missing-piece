"""S4, CPU half of the probe-isolation check: every development scenario, all four cells, two models' serializers,
mock backend. Pass = every game byte-identical with and without probes AND every negative control detected.
Writes gates/S4/results/isolation_cpu.json. The GPU half (same function, one server start per model) is in S4_PLAN.md."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from mp.assign import make_plan  # noqa: E402
from mp.backend import MockBackend  # noqa: E402
from mp import isolation  # noqa: E402

rows = []
for f in sorted((HERE.parents[1] / "gates/S1/banks/development").glob("*.json")):
    spec = json.loads(f.read_text())
    for model in ("gemma-2-9b-it", "qwen3.5-27b"):
        plan = make_plan(spec, model, 0, rounds=4, tag="s4cpu")
        for cell in ("UA", "UP", "KA", "KP"):
            rows.append(isolation.check(spec, plan, cell, lambda: MockBackend(model)))
ok = all(r["identical_with_probes"] for r in rows) and all(r["negative_control_detected"] for r in rows)
out = {"games": len(rows), "identical": sum(r["identical_with_probes"] for r in rows),
       "negative_controls_detected": sum(r["negative_control_detected"] for r in rows),
       "live_calls_compared": sum(r["live_calls"] for r in rows), "probes_run": sum(r["probes_run"] for r in rows),
       "pass": ok, "rows": rows}
(HERE / "results").mkdir(exist_ok=True)
(HERE / "results" / "isolation_cpu.json").write_text(json.dumps(out, indent=1) + "\n")
print({k: v for k, v in out.items() if k != "rows"})
