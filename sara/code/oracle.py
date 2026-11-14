"""Avaliação independente com SWI-Prolog e substituições formais revisadas."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from prepare import ARCHIVE, PRIVATE, digest, write


def parts(source):
    facts, tail = source.split("% Facts", 1)[1].split("% Test", 1)
    query = re.fullmatch(r"\s*:-\s*(.*?)\.\s*:-\s*halt\.\s*", tail, re.S).group(1)
    return facts, query.removeprefix("\\+").strip()


def run(swipl, root, facts, query):
    script = root / "audit.pl"
    script.write_text(facts + "\n", encoding="utf8")
    proc = subprocess.run([swipl, "-q", "-s", str(script), "-g",
                           f"(({query})->write(sara_true);write(sara_false))", "-t", "halt"],
                          cwd=root, capture_output=True, text=True, timeout=30)
    out = proc.stdout.strip()
    if proc.returncode or "ERROR:" in proc.stderr or out not in ("sara_true","sara_false"):
        raise ValueError(proc.stderr or out or "Falha no Prolog")
    return out == "sara_true"


def audit(folder, reviews, swipl):
    gold = json.loads((PRIVATE / "gold.json").read_text())
    ids = json.loads((folder / "manifest.json").read_text())["ids"]
    rows = []
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(ARCHIVE) as t:
        root = Path(tmp)
        for item in t:
            path = Path(item.name)
            if item.isfile() and item.name.startswith("sara/statutes/prolog/") and path.suffix == ".pl" and not path.name.startswith("."):
                target = root / path.relative_to("sara")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(t.extractfile(item).read())
        for key in ids:
            record = gold[key]
            src = t.extractfile("sara/cases/" + record["name"] + ".pl").read().decode()
            facts, query = parts(src)
            original = run(swipl, root, facts, query)
            row = dict(id=key, original=original, reproduced=original == record["label"], edits={})
            trial = json.loads((folder / (key + ".json")).read_text(encoding="utf8"))
            for author, edit in trial["edits"].items():
                review = reviews.get(key, {}).get(author)
                if not review:
                    continue
                if review["text_sha256"] != digest(edit["text"]):
                    raise ValueError("Revisão de outra edição")
                old, new = review["old_facts"], review["new_facts"]
                if not old.strip() or facts.count(old) != 1:
                    raise ValueError("Trecho formal ambíguo ou ausente")
                after = run(swipl, root, facts.replace(old, new, 1), query)
                row["edits"][author] = dict(after=after, flip=after != original)
            rows.append(row)
    write(folder / "oracle.json", rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path)
    p.add_argument("--reviews", type=Path)
    p.add_argument("--swipl", default="swipl")
    a = p.parse_args()
    audit(a.folder, json.loads(a.reviews.read_text(encoding="utf8")) if a.reviews else {}, a.swipl)
