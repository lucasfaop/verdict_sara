"""Piloto de decisão com política fornecida. Executar da raiz do projeto."""
import argparse
import json
import re
import z3
from run import EXTRACT, Model, PUBLIC, ROOT, digest, load, symbolic, write

POLICIES = {
    "7703(b)(2)": {
        "source": "such individual furnishes over one-half of the cost of maintaining such household during the taxable year",
        "variables": {"majority_cost": {"type": "Bool", "meaning":
            "The person named in the hypothesis furnished more than half the cost of maintaining the home in the specified year. Extract the reported maintenance contribution. Use null when unsupported."}},
        "rule": "majority_cost",
    },
    "63(f)(1)(a)": {
        "source": "for himself if he has attained age 65 before the close of his taxable year",
        "variables": {"birth_year": {"type": "Int", "meaning":
            "Calendar year of birth of the person named in the hypothesis. If a partial birth date leaves their age at year end uncertain, use null."}},
        "rule": [">=", ["-", "YEAR", "birth_year"], 65],
    },
}


from policy_catalog import CATALOG

# Preserve the extraction schema used in the initial four-case comparison.
POLICIES = {**CATALOG, **POLICIES}
FULL_EXTRACT = """Extract only the requested factual inputs from the narrative, for the person,
time and proposition in the hypothesis. Return a JSON object with a facts object keyed by
the exact variable names supplied. Each entry has value (boolean, number or null) and quote
(exact unique or nonunique narrative substring supporting that value). Use null for unsupported
facts. Do not answer the hypothesis or take its claimed amount as evidence."""


def bind(hypothesis):
    sections = re.findall(r"\bsection\s+(\d+(?:\([a-z0-9]+\))*)", hypothesis, re.I)
    if len(sections) != 1 or sections[0].lower() not in POLICIES:
        raise ValueError(f"Dispositivo não coberto ou ambíguo: {hypothesis}")
    key = sections[0].lower()
    policy = POLICIES[key]
    amounts = re.findall(r"\$([\d,]+)(?!\d|\.\d)", hypothesis)
    years = re.findall(r"\b(?:19|20)\d{2}\b", hypothesis)

    def resolve(node):
        if node == ["INTEGRAL_BAND"]:
            return (2000 - int(amounts[0].replace(",", ""))) % 40 == 0
        if isinstance(node, list):
            return [resolve(child) for child in node]
        if node == "OPTIONAL_250K":
            return not amounts or int(amounts[0].replace(",", "")) == 250000
        if node == "YEAR" and len(years) == 1:
            return int(years[0])
        if node == "AMOUNT" and len(amounts) == 1:
            return int(amounts[0].replace(",", ""))
        if node in ("YEAR", "AMOUNT"):
            raise ValueError(f"Parâmetro {node} ausente ou ambíguo: {hypothesis}")
        return node

    return key, dict(variables=policy["variables"], rule=resolve(policy["rule"]))


if __name__ == "__main__":

    from collections import Counter
    from pathlib import Path
    import run

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-5-nano-2025-08-07")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    laws = load(PUBLIC / "statutes.json")
    for key, policy in POLICIES.items():
        if policy["source"] not in laws:
            raise ValueError(f"Fonte não encontrada: {key}")
    cases = load(PUBLIC / "test.json")
    selected = [(c, bind(c["hypothesis"])) for c in cases]
    counts = Counter(key for _, (key, _) in selected)
    if len({c["id"] for c in cases}) != 100 or set(counts) != set(POLICIES) or set(counts.values()) != {2}:
        raise ValueError(f"Cobertura inesperada: {counts}")
    print(f"{len(selected)} casos, {len(counts)} dispositivos", flush=True)
    model = Model(args.model)
    manifest = dict(model=args.model, endpoint=model.base, policies=POLICIES,
                    extract=FULL_EXTRACT, statutes_hash=digest(laws), cases_hash=digest(json.dumps(selected)),
                    code=digest(Path(__file__).read_text(encoding="utf8")), solver=z3.get_version_string(),
                    solver_adapter=digest(Path(run.__file__).read_text(encoding="utf8")),
                    ids=[c["id"] for c, _ in selected], split="test")
    folder = ROOT / "results" / ("politica-fornecida-" + digest(json.dumps(manifest))[:12])
    if args.check:
        for case, (_, program) in selected:
            for known in (False, True):
                facts = {}
                for name, spec in program["variables"].items():
                    value = (True if spec["type"] == "Bool" else 1) if known else None
                    facts[name] = dict(value=value, quote="fixture")
                symbolic(program, facts, "fixture")
        print("100 fórmulas resolvidas com entradas sintéticas conhecidas e desconhecidas; nenhuma chamada à API.")
    else:
        write(folder / "manifest.json", manifest)
        print(folder, flush=True)
        for index, (case, (section, program)) in enumerate(selected, 1):
            output = folder / (case["id"] + ".json")
            if not output.exists():
                try:
                    if program["variables"]:
                        context = dict(statutes=laws, text=case["text"], hypothesis=case["hypothesis"],
                                       variables=program["variables"])
                        facts = model.ask(FULL_EXTRACT, context)["facts"]
                        if len(program["variables"]) == 1 and set(facts) == {"v1"}:
                            facts = {next(iter(program["variables"])): facts["v1"]}
                    else:
                        facts = {}
                    result = symbolic(program, facts, case["text"])
                except (ValueError, KeyError, TypeError, AttributeError, z3.Z3Exception) as exc:
                    result = dict(decision=None, error=str(exc))
                write(output, dict(section=section, program=program, result=result))
            print(f"{index}/{len(selected)}", flush=True)
        from evaluate import evaluate
        evaluate(folder)
        print(folder)

