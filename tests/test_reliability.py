"""mp.reliability reproduces Paper 1's agreement functions exactly (source file in the edsl_wwil clone, if present)."""
import ast
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mp import reliability as R  # noqa: E402

SRC = Path("/home/user/randallspqr/edsl_wwil/two_truths_lie_study/two_truths_lie/results/perfect_lie/"
           "prefreeze_checks/analysis/prefreeze_agreement.py")


@pytest.mark.skipif(not SRC.exists(), reason="Paper 1 source not cloned")
def test_matches_paper1_source():
    tree = ast.parse(SRC.read_text())
    ns = {"np": np}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("kappa", "ac1", "boot"):
            exec(compile(ast.Module([node], []), str(SRC), "exec"), ns)
    rng = np.random.default_rng(3)
    for p in (0.05, 0.3, 0.5):
        a = rng.random(300) < p
        b = np.where(rng.random(300) < 0.85, a, ~a)
        assert R.kappa(a, b) == ns["kappa"](a, b) and R.ac1(a, b) == ns["ac1"](a, b)
        assert np.array_equal(R.boot(a, b, R.kappa), ns["boot"](a, b, ns["kappa"]))
        assert np.array_equal(R.boot(a, b, R.ac1), ns["boot"](a, b, ns["ac1"]))


def test_gate_rule():
    rng = np.random.default_rng(1)
    ids = [f"i{k}" for k in range(400)]
    truth = {i: rng.random() < 0.3 for i in ids}
    rare = {i: rng.random() < 0.02 for i in ids}
    P = {i: {"good": truth[i], "bad": rng.random() < 0.3, "rare": rare[i]} for i in ids}
    G = {i: {"good": truth[i] if rng.random() < 0.97 else not truth[i], "bad": rng.random() < 0.3, "rare": rare[i]} for i in ids}
    g = R.gate(P, G, ["good", "bad", "rare"])
    assert not g["good"]["excluded"] and g["bad"]["excluded"]
    assert g["rare"]["flagged"] and not g["rare"]["gated"] and not g["rare"]["excluded"]
