"""Avaliação posterior à inferência."""
import argparse
from collections import Counter
from pathlib import Path
from prepare import PRIVATE, write
from run import load


def evaluate(folder):
    manifest = load(folder / "manifest.json")
    gold = load(PRIVATE / "gold.json")
    ids = manifest["ids"]
    if "policies" in manifest:
        decisions = [load(folder / (key + ".json"))["result"]["decision"] for key in ids]
        correct = sum(value is gold[key]["label"] for key, value in zip(ids, decisions))
        stats = {"supplied_policy": dict(correct=correct, total=len(ids),
                                         abstain_or_error=decisions.count(None),
                                         accuracy=correct / len(ids))}
        baseline = folder.parent / "test-dd4ec1fe5cf1"
        if (baseline / "manifest.json").is_file():
            frozen = load(baseline / "manifest.json")
            if (manifest["model"] == frozen["model"] and manifest["endpoint"] == frozen["endpoint"]
                    and manifest["statutes_hash"] == frozen["laws"] and set(ids) <= set(frozen["ids"])):
                paired = Counter()
                for key, value in zip(ids, decisions):
                    label = gold[key]["label"]
                    old = load(baseline / (key + ".json"))["originals"]
                    for arm in ("direct", "verdict"):
                        paired[arm + "_correct"] += old[arm]["decision"] is label
                    previous = old["verdict"]["decision"]
                    paired["positive_recovered"] += label and value is True and previous is not True
                    paired["positive_lost"] += label and previous is True and value is not True
                    paired["new_false_positive"] += not label and value is True and previous is not True
                    paired["previously_correct_now_wrong_or_missing"] += previous is label and value is not label
                    paired["supplied_true_positive"] += label and value is True
                    paired["supplied_false_positive"] += not label and value is True
                stats["paired_vs_frozen"] = dict(paired)
        write(folder / "metrics.json", stats)
        print(stats)
        return
    stats = {}
    for arm in ("direct", "verdict"):
        c = Counter()
        for key in ids:
            record = load(folder / (key + ".json"))
            original = record["originals"][arm]["decision"]
            c["correct"] += original is gold[key]["label"]
            c["abstain_or_error"] += original is None
            for author, edit in record["edits"].items():
                after = edit["predictions"][arm]["decision"]
                c[author + "_edits"] += 1
                if type(original) is bool and type(after) is bool:
                    c[author + "_comparable"] += 1
                    c[author + "_flips"] += original != after
        stats[arm] = dict(c, total=len(ids), accuracy=c["correct"]/len(ids))
    write(folder / "metrics.json", stats)
    print(stats)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    folder = parser.parse_args().folder
    if not (folder / "manifest.json").is_file():
        results = Path(__file__).resolve().parents[1] / "results"
        runs = sorted(str(path.parent) for path in results.glob("*/manifest.json"))
        parser.error(f"Manifesto ausente em {folder}. Execuções disponíveis: "
                     + (", ".join(runs) or "nenhuma"))
    evaluate(folder)
