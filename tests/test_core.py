import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mp import analysis as A  # noqa: E402
from mp import evidence as ev  # noqa: E402
from mp import isolation  # noqa: E402
from mp.assign import make_plan  # noqa: E402
from mp.backend import MockBackend  # noqa: E402
from mp.protocol import Settings, briefings, run_game  # noqa: E402
from mp.simulate import SimParams, simulate  # noqa: E402

DEV = sorted((ROOT / "gates/S1/banks/development").glob("*.json"))


def spec(i=0):
    return json.loads(DEV[i].read_text())


def test_pooled_benchmark_values():
    s = spec()
    p = s["evidence_model"]["pooled"]
    ln = math.log
    assert p["UA"]["group_toward_truth"] == pytest.approx(-ln(3), abs=1e-6)
    for c in ("UP", "KA", "KP"):
        assert p[c]["group_toward_truth"] == pytest.approx(ln(49) - ln(3), abs=1e-6)   # record counted once in KP
    assert p["UA"]["receivers_toward_truth"] == pytest.approx(0, abs=1e-9)
    assert s["evidence_model"]["solvable_verifier_present"]


def test_dependence_group_counted_once():
    items = [{"item_id": "x", "favours": "A", "accuracy": "3/4", "dependence_group": "g"},
             {"item_id": "y", "favours": "A", "accuracy": "9/10", "dependence_group": "g"},
             {"item_id": "x", "favours": "A", "accuracy": "3/4", "dependence_group": "g"}]
    assert ev.pooled_logodds(items, 0.5, "A") == pytest.approx(math.log(9))


def test_banks_reproduce_and_validate():
    before = (ROOT / "gates/S1/banks/MANIFEST.json").read_text()
    subprocess.run([sys.executable, str(ROOT / "gates/S1/make_banks.py")], check=True, capture_output=True)
    assert (ROOT / "gates/S1/banks/MANIFEST.json").read_text() == before


def test_lint_passes():
    r = subprocess.run([sys.executable, str(ROOT / "gates/S2/lint.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]


def test_same_report_all_cells_and_only_record_line_differs():
    s = spec(3)
    plan = make_plan(s, "gemma-2-9b-it", 0, 4)
    B = {c: briefings(s, plan, c, "MP-W1") for c in ev.CELLS}
    rep = next(i for i in s["evidence_model"]["items"] if i["item_id"] == "report")["text"]
    assert all(rep in B[c][plan.speaker] for c in ev.CELLS)
    diff = [x for x, y in zip(B["UA"][plan.speaker].split("\n"), B["KA"][plan.speaker].split("\n")) if x != y]
    assert len(diff) == 1


def test_isolation_and_negative_control():
    s = spec(5)
    r = isolation.check(s, make_plan(s, "qwen3.5-9b", 1, 4), "KP", lambda: MockBackend("qwen3.5-9b"))
    assert r["identical_with_probes"] and r["negative_control_detected"]


def test_roles_never_named_in_live_prompts():
    s = spec(2)
    rec = run_game(s, make_plan(s, "gemma-3-27b-it", 0, 2), "KP", MockBackend("gemma-3-27b-it"), Settings(rounds=2))
    assert rec["receiver_support"] in (0, 0.25, 0.5, 0.75, 1.0)
    b = MockBackend("gemma-3-27b-it")
    g_text = " ".join(briefings(s, make_plan(s, "x", 0, 2), "KP", "MP-W1").values()).lower()
    for w in ("speaker", "verifier", "advocate", "receiver"):
        assert w not in g_text


def test_vote_prompt_strict_instruction():
    from mp.prompts import WORDINGS
    assert WORDINGS["MP-W1"]["vote"].endswith("Reply with exactly one letter, A or B, and nothing else.")


def test_analysis_recovers_sign():
    w = A.quads(A.frame(simulate(SimParams(n_stories=30, delta_K=0.15), seed=4)))
    assert A.paired(w)["estimate"] > 0.05


def test_manifest_requires_server_start():
    from mp import manifest
    with pytest.raises(ValueError):
        manifest.header("gemma-2-9b-it")
