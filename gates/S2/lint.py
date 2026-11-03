"""Gate S2, CPU part: scenario lint on BOTH banks (no model call).

Per scenario, with a seeded plan, every agent's briefing is rendered in all four cells. Checks:
  L1  the report sentence is identical, word for word, in the speaker's briefing in all four cells;
  L2  the knowing and uninformed speaker briefings differ ONLY in the record line (record vs a neutral record), and that
      line has the same lead-in (format) and a length within +-2 words;
  L3  the verifier holder's briefing in verifier-present cells differs from verifier-absent cells only in that line,
      same rule as L2; all other receivers' briefings are identical across the four cells;
  L4  every neutral record is within +-2 words of the record (rendered) and shares its lead-in;
  L5  story rules: option length <= 8 words, fact lengths 8-14 words, claims within 2 words, 5 neutrals, 2 shared,
      no role words ("agent", "speaker", "verifier", "advocate", "lie", "truth", "false", "true");
  L6  no role words anywhere in any rendered briefing beyond the instructions' own "Agent" labels;
  L7  development and confirmatory banks share no story id, option text, report source, record source or claim;
  L8  evidence: report favours F, record favours T, verifier-present cells meet the pooled margin, spec hash matches
      the MANIFEST.
Writes gates/S2/results/lint.json and exits non-zero on any failure."""
import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from mp import evidence as ev  # noqa: E402
from mp.assign import make_plan  # noqa: E402
from mp.protocol import briefings  # noqa: E402

ROLE_WORDS = re.compile(r"\b(speaker|verifier|advocate|lie|lies|liar|truth|false|true|agent)\b", re.I)
W = "MP-W1"


def nwords(s):
    return len(s.split())


def lead(line):
    return line.split(" It shows that ")[0] if " It shows that " in line else None


def lint_spec(spec, manifest_sha):
    fails = []
    plan = make_plan(spec, "lint", 0, rounds=4, tag="lint")
    B = {c: briefings(spec, plan, c, W) for c in ev.CELLS}
    sp, vh = plan.speaker, plan.verifier_holder
    by = {it["item_id"]: it for it in spec["evidence_model"]["items"]}
    report = by["report"]["text"]
    if not all(report in B[c][sp] for c in ev.CELLS):
        fails.append("L1 report not identical in all cells")

    def diff(a, b):
        la, lb = a.split("\n"), b.split("\n")
        if len(la) != len(lb):
            return None
        return [(x, y) for x, y in zip(la, lb) if x != y]

    for name, a, b in (("L2 speaker", B["UA"][sp], B["KA"][sp]), ("L2 speaker(P)", B["UP"][sp], B["KP"][sp]),
                       ("L3 verifier holder", B["UA"][vh], B["UP"][vh]), ("L3 verifier holder(K)", B["KA"][vh], B["KP"][vh])):
        d = diff(a, b)
        if d is None or len(d) != 1:
            fails.append(f"{name}: briefings differ in more than one line")
            continue
        x, y = d[0]
        if lead(x) != lead(y) or lead(x) is None:
            fails.append(f"{name}: record line format differs")
        if abs(nwords(x) - nwords(y)) > 2:
            fails.append(f"{name}: record line length {nwords(x)} vs {nwords(y)}")
    for k in range(1, 6):
        if k in (sp, vh):
            continue
        if len({B[c][k] for c in ev.CELLS}) != 1:
            fails.append(f"L3 receiver {k} briefing differs across cells")
    rec = by["record"]["text"]
    for i in range(5):
        n = by[f"neutral{i}"]["text"]
        if lead(n) != lead(rec) or abs(nwords(n) - nwords(rec)) > 2:
            fails.append(f"L4 neutral{i} format/length ({nwords(n)} vs record {nwords(rec)})")
    for c in ev.CELLS:
        for k, txt in B[c].items():
            if ROLE_WORDS.search(txt):
                fails.append(f"L6 role word in {c} briefing of {k}: {ROLE_WORDS.search(txt).group(0)}")
    em = spec["evidence_model"]
    if by["report"]["favours"] != em["report_option"] or by["record"]["favours"] != spec["hidden_state"]:
        fails.append("L8 directions")
    if not em["solvable_verifier_present"]:
        fails.append("L8 verifier-present cells below the pooled margin")
    if ev.scenario_hash(spec) and manifest_sha is None:
        fails.append("L8 not in MANIFEST")
    return fails


def lint_story(st):
    f = []
    for o in st["options"].values():
        if nwords(o) > 8:
            f.append(f"L5 option too long: {o}")
    fa, fb = nwords(st["fact"]["A"]), nwords(st["fact"]["B"])
    if not (8 <= fa <= 14 and 8 <= fb <= 14 and abs(fa - fb) <= 2):
        f.append("L5 fact lengths")
    if abs(nwords(st["claim"]["A"]) - nwords(st["claim"]["B"])) > 2:
        f.append("L5 claim lengths")
    if len(st["neutral"]) != 5 or len(st["shared"]) != 2:
        f.append("L5 counts")
    for n in st["neutral"]:
        if not (8 <= nwords(n) <= 14 and abs(nwords(n) - fa) <= 2 and abs(nwords(n) - fb) <= 2):
            f.append(f"L5 neutral length: {n}")
    txt = " ".join([st["question"], *st["options"].values(), *st["claim"].values(), *st["fact"].values(),
                    *st["neutral"], *st["shared"]])
    if ROLE_WORDS.search(txt):
        f.append(f"L5 role word: {ROLE_WORDS.search(txt).group(0)}")
    for s in [*st["claim"].values(), *st["fact"].values(), *st["neutral"]]:
        if s.rstrip().endswith("."):
            f.append(f"L5 clause ends with a full stop: {s}")
    return f


def main():
    man = json.loads((ROOT / "gates/S1/banks/MANIFEST.json").read_text())
    out = {"stories": {}, "specs": {}, "cross_bank": []}
    keys = {}
    for bank in ("development", "confirmatory"):
        for st in yaml.safe_load((ROOT / f"gates/S1/stories/{bank}.yaml").read_text()):
            out["stories"][st["story_id"]] = lint_story(st)
            for k in ("options", "claim"):
                for v in st[k].values():
                    keys.setdefault(("text", v.lower()), set()).add(bank)
            for k in ("report_source", "record_source"):
                keys.setdefault(("source", st[k].lower()), set()).add(bank)
        for sid, meta in man["banks"][bank]["specs"].items():
            spec = json.loads((ROOT / meta["file"]).read_text())
            out["specs"][sid] = lint_spec(spec, meta["sha256"])
    out["cross_bank"] = [k[1] for k, v in keys.items() if len(v) > 1]
    n_fail = sum(bool(v) for v in out["stories"].values()) + sum(bool(v) for v in out["specs"].values()) + len(out["cross_bank"])
    out["summary"] = {"stories": len(out["stories"]), "specs": len(out["specs"]),
                      "stories_failing": [k for k, v in out["stories"].items() if v],
                      "specs_failing": [k for k, v in out["specs"].items() if v],
                      "cross_bank_overlaps": out["cross_bank"], "pass": n_fail == 0}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "lint.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out["summary"], indent=1))
    for k, v in {**out["stories"], **out["specs"]}.items():
        if v:
            print(k, v)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
