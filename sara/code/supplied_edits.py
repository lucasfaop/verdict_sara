"""Generate supplied-policy interventions and re-extract facts from the edited narratives."""
import argparse
from pathlib import Path

from run import EDIT, PUBLIC, ROOT, Model, digest, load, symbolic, write
from supplied_policy import FULL_EXTRACT
import z3


def execute(folder):
    manifest = load(folder / "manifest.json")
    if manifest.get("extract") != FULL_EXTRACT:
        raise ValueError("Extrator diferente da execução congelada.")
    laws = load(PUBLIC / "statutes.json")
    if digest(laws) != manifest["statutes_hash"]:
        raise ValueError("Legislação diferente da execução congelada.")
    model = Model(manifest["model"])
    if model.base != manifest["endpoint"]:
        raise ValueError("Use o endpoint da execução original.")
    cases = {c["id"]: c for c in load(PUBLIC / "test.json")}
    dest = folder / "counterfactuals"
    for index, key in enumerate(manifest["ids"], 1):
        path = dest / (key + ".json")
        if path.exists():
            continue
        record = load(folder / (key + ".json"))
        original = record["result"]
        program = record["program"]
        pivotal = original.get("trace", {}).get("pivotal", [])
        case = cases[key]
        result = dict(id=key, original=original["decision"], pivotal=pivotal)
        if original["decision"] is None or not pivotal:
            result["status"] = "ineligible"
        else:
            ctx = dict(statutes=laws, text=case["text"], hypothesis=case["hypothesis"])
            try:
                edit = model.ask(EDIT, dict(**ctx, rule=program["rule"], variables=program["variables"],
                                           facts=original["facts"], pivotal=pivotal, decision=original["decision"]))
                result["proposal"] = edit
                old, new = edit.get("old"), edit.get("new")
                if isinstance(old,str) and old.strip() and ctx["text"].count(old)==1 and isinstance(new,str) and new.strip() and new!=old:
                    ctx["text"] = ctx["text"].replace(old,new,1)
                    result.update(text=ctx["text"], text_sha256=digest(ctx["text"]))
                    values = model.ask(FULL_EXTRACT, dict(**ctx, variables=program["variables"]))["facts"]
                    if len(program["variables"]) == 1 and set(values) == {"v1"}:
                        values = {next(iter(program["variables"])):values["v1"]}
                    result["after"] = symbolic(program, values, ctx["text"])
                    result["status"] = "edited"
                else:
                    result["status"] = "no_edit"
            except (ValueError, TypeError, KeyError, AttributeError, z3.Z3Exception) as exc:
                result.update(status="error", error=str(exc))
        write(path,result)
        print(f"{index}/{len(manifest['ids'])} {result['status']}",flush=True)
    print(dest)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("folder",nargs="?",type=Path,default=ROOT/"results/politica-fornecida-bb7055fdc7ff")
    execute(parser.parse_args().folder)
