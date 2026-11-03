"""Gate S1: build the development and confirmatory scenario banks from the story files, validate every spec against
the shared evidence schema v1.0 plus Missing Piece's own checks, and write the banks and their MANIFEST (sha256 of
every file). Deterministic: re-running reproduces every file byte for byte. No model is called.

Development bank: 12 stories x truth {A, B} = 24 core specs + 8 conditional-challenge variants (4 stories x 2 truths;
a shared weak 3/5 report for the false option, held by all five agents). Confirmatory bank: 26 stories x truth {A, B}
= 52 specs, no challenge variants, stories and options disjoint from development."""
import hashlib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from mp import evidence as ev  # noqa: E402

SCHEMA = json.loads((HERE / "schema" / "evidence_schema_v1.0.json").read_text())
CHALLENGE_STORIES = ["dev-clinic-nurse-cert", "dev-ferry-timetable", "dev-museum-painting-loan", "dev-farm-irrigation-permit"]


def dump(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def main():
    out = HERE / "banks"
    manifest = {"schema": {"file": "gates/S1/schema/evidence_schema_v1.0.json",
                           "sha256": hashlib.sha256((HERE / "schema" / "evidence_schema_v1.0.json").read_bytes()).hexdigest(),
                           "coordination_commit": "9c155beb9054a9b639d41d0b92d1dfce11f81ac1"},
                "stories": {}, "banks": {}}
    problems = []
    for bank, fname in (("development", "development.yaml"), ("confirmatory", "confirmatory.yaml")):
        f = HERE / "stories" / fname
        manifest["stories"][bank] = {"file": f"gates/S1/stories/{fname}", "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
        stories = yaml.safe_load(f.read_text())
        files = {}
        for st in stories:
            variants = [(t, False) for t in "AB"]
            if bank == "development" and st["story_id"] in CHALLENGE_STORIES:
                variants += [(t, True) for t in "AB"]
            for truth, ch in variants:
                spec = ev.build_scenario(st, truth, bank, challenge=ch)
                pr = ev.validate(spec, SCHEMA)
                if pr:
                    problems.append((spec["scenario_id"], pr))
                p = out / bank / f"{spec['scenario_id']}.json"
                dump(spec, p)
                files[spec["scenario_id"]] = {"file": str(p.relative_to(HERE.parents[1])),
                                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                              "story_id": st["story_id"], "truth": truth, "challenge_set": ch}
        manifest["banks"][bank] = {"n_specs": len(files), "n_stories": len(stories), "specs": files}
    dev_ids = {v["story_id"] for v in manifest["banks"]["development"]["specs"].values()}
    conf_ids = {v["story_id"] for v in manifest["banks"]["confirmatory"]["specs"].values()}
    assert not dev_ids & conf_ids, "development and confirmatory stories overlap"
    dump(manifest, out / "MANIFEST.json")
    print(json.dumps({b: {"n_specs": manifest["banks"][b]["n_specs"], "n_stories": manifest["banks"][b]["n_stories"]}
                      for b in manifest["banks"]}), "problems:", problems or "none")
    print("MANIFEST sha256", hashlib.sha256((out / "MANIFEST.json").read_bytes()).hexdigest())
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
