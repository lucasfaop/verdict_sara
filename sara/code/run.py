"""Inferência SARA. Lê apenas o corpus público."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import requests
import z3
from prepare import PUBLIC, ROOT, digest, write

sys.path.insert(0, str(ROOT.parent / "vendor/verdict"))
from smt_core.maxsmt import Condition, OBSERVED, UNRESOLVED, solve

DIRECT = """Decide whether the hypothesis follows under these statutes. Return JSON
{"decision":true or false,"old":"exact unique factual span","new":"minimal replacement
predicted to reverse the decision"}. Use null spans if no grounded intervention exists."""
COMPILE = """Compile the statutory test for this hypothesis independently of case facts.
Return JSON {"variables":{"v1":{"type":"Bool","meaning":"factual input with entity,
date and units"}}, "target":"exact cited provision and proposition tested", "rule": expression}. Set type to exactly Bool, Real or Int. Use as many factual inputs as needed. Resolve
cross-references and exceptions within the scope of the exact proposition. Include ancestor or
sibling conditions only when the proposition actually requires them. Distinguish testing a
clause from testing the full classification. Permit expressly stated legal statuses as inputs. Do not use the final legal conclusion as an input.
An expression is a variable name, integer, boolean, or a nested JSON list with operator
and operands. Allowed operators: and, or, not, =, <, <=, >, >=, +, -, *, /, ite.
Use integer constants and rational division for decimals. The final expression is Boolean."""
EXTRACT = """Extract values for the supplied variables from the narrative. Return JSON
{"facts":{"v1":{"value":true or false or number or null,"quote":"exact narrative span"}}}.
For missing evidence use null. Keep inferred legal conclusions out of factual inputs."""
EDIT = """Use the supplied rule, facts and pivotal variables to find a minimal factual change
that suffices to reverse the decision on the exact hypothesis. Evaluate the entire rule under
the proposed values. Hold other observed facts fixed and leave unobserved facts unknown:
the opposite decision must follow for every compatible assignment. Check other requirements,
alternatives and exceptions. Express the change in one unique narrative span; several values
may change together if necessary. Preserve the statutes and hypothesis. Return JSON with old
(exact span), new (replacement) and changes (list of objects with variable, before, after).
If no grounded replacement suffices, return null spans and an empty list."""


def load(path):
    return json.loads(path.read_text(encoding="utf8"))


class Model:
    def __init__(self, name):
        self.name = name
        self.base = os.getenv("PILOT_API_BASE", "https://api.openai.com/v1").rstrip("/")
        self.key = os.getenv("PILOT_API_KEY") or os.getenv("OPENAI_API_KEY")

    def ask(self, prompt, content):
        payload = dict(model=self.name, response_format={"type":"json_object"},
                       messages=[dict(role="system", content=prompt),
                                 dict(role="user", content=json.dumps(content, ensure_ascii=False))])
        key = digest(json.dumps([self.base, payload], sort_keys=True))
        path = ROOT / "results/cache" / (key + ".json")
        if not path.exists():
            if not self.key:
                raise SystemExit("Defina PILOT_API_KEY ou OPENAI_API_KEY.")
            for attempt in range(2):
                try:
                    response = requests.post(self.base + "/chat/completions", json=payload,
                                             headers={"Authorization":"Bearer " + self.key},
                                             timeout=(15, 360))
                    break
                except requests.exceptions.ReadTimeout:
                    if attempt == 1:
                        raise SystemExit("Timeout de leitura após duas tentativas. Repita o comando para retomar pelo cache.")
                    print("Timeout de leitura. Repetindo a chamada uma vez.", file=sys.stderr, flush=True)
            if not response.ok:
                try:
                    detail = response.json()["error"]["message"]
                except (ValueError, KeyError, TypeError):
                    detail = response.reason
                raise SystemExit(f"API HTTP {response.status_code}: {detail}")
            write(path, dict(request=payload, response=response.json()))
        result = load(path)["response"]["choices"][0]["message"]["content"]
        value = json.loads(result)
        if not isinstance(value, dict):
            raise ValueError("Esperado objeto JSON")
        return value


OPS = {"and","or","not","=","<","<=",">",">=","+","-","*","/","ite"}


def expression(node, variables):
    if type(node) in (int, bool):
        return str(node).lower()
    if isinstance(node, str) and node in variables:
        return f"|{node}|"
    if isinstance(node, list) and node and node[0] in OPS:
        return "(" + " ".join([node[0]] + [expression(n, variables) for n in node[1:]]) + ")"
    raise ValueError("Expressão inválida")


def symbolic(program, extracted, text):
    variables = program["variables"]
    declarations, conditions = [], []
    for name, spec in variables.items():
        value = extracted[name]["value"]
        sort = spec["type"]
        if sort == "Integer":
            sort = "Int"
        if sort == "Bool or Real" and type(value) in (bool, float, int):
            sort = "Bool" if type(value) is bool else "Real"
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or sort not in ("Bool", "Real", "Int"):
            raise ValueError("Variável inválida")
        declarations.append(f"(declare-const |{name}| {sort})")
        fact = extracted[name]
        value = fact["value"]
        if value is not None:
            valid = type(value) is bool if sort == "Bool" else type(value) in (int, float)
            if sort == "Int" and type(value) is not int:
                valid = False
            if not valid or not fact["quote"] or fact["quote"] not in text:
                raise ValueError("Evidência ou tipo inválido")
        conditions.append(Condition(name, value, OBSERVED if value is not None else UNRESOLVED))
    rule = expression(program["rule"], variables)
    yes = solve(declarations + [f"(assert {rule})"], conditions)
    no = solve(declarations + [f"(assert (not {rule}))"], conditions)
    # Entailment requires the negation to be impossible under the observed facts.
    determined = yes.status == no.status == "ok" and yes.decision != no.decision
    return dict(decision=(yes.decision == "eligible") if determined else None,
                trace=asdict(yes), negated=asdict(no), facts=extracted)


def predict(model, arm, context, propose):
    if arm == "direct":
        out = model.ask(DIRECT, context)
        if type(out.get("decision")) is not bool:
            raise ValueError("Decisão inválida")
        return out
    program = model.ask(COMPILE, {k:context[k] for k in ("statutes","hypothesis")})
    facts = model.ask(EXTRACT, dict(**context, variables=program["variables"]))["facts"]
    out = symbolic(program, facts, context["text"])
    out["program"] = program
    if propose and out["decision"] is not None and out["trace"]["pivotal"]:
        edit = model.ask(EDIT, dict(**context, rule=program["rule"], variables=program["variables"], facts=facts,
                                    pivotal=out["trace"]["pivotal"], decision=out["decision"]))
        out.update(old=edit.get("old"), new=edit.get("new"), changes=edit.get("changes"))
    return out


def trial(model, context):
    arms = ("direct", "verdict")
    def safe(arm, case, propose):
        try:
            return predict(model, arm, case, propose)
        except (ValueError, KeyError, TypeError, IndexError, z3.Z3Exception) as exc:
            return dict(decision=None, error=str(exc))
    originals = {arm:safe(arm, context, True) for arm in arms}
    edits = {}
    for author, result in originals.items():
        old, new = result.get("old"), result.get("new")
        if isinstance(old, str) and old.strip() and context["text"].count(old) == 1 and isinstance(new, str) and new.strip() and new != old:
            edited = dict(context, text=context["text"].replace(old, new, 1))
            edits[author] = dict(text=edited["text"], predictions={arm:safe(arm, edited, False) for arm in arms})
    return dict(originals=originals, edits=edits)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--split", choices=["pilot","train","test"], default="pilot")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cases = load(PUBLIC / (args.split + ".json"))
    if args.limit is not None and not 1 <= args.limit <= len(cases):
        parser.error("--limit fora do intervalo")
    cases = cases[:args.limit]
    laws = load(PUBLIC / "statutes.json")
    model = Model(args.model)
    manifest = dict(split=args.split, ids=[c["id"] for c in cases], model=args.model, endpoint=model.base,
                    laws=digest(laws), cases=digest(json.dumps(cases)), code=digest(Path(__file__).read_text(encoding="utf8")),
                    solver=z3.get_version_string(), core=hashlib.sha256((ROOT.parent / "vendor/verdict/smt_core/maxsmt.py").read_bytes()).hexdigest())
    folder = ROOT / "results" / (args.split + "-" + digest(json.dumps(manifest))[:12])
    write(folder / "manifest.json", manifest)
    for i, case in enumerate(cases, 1):
        output = folder / (case["id"] + ".json")
        if not output.exists():
            write(output, trial(model, dict(statutes=laws, text=case["text"], hypothesis=case["hypothesis"])))
        print(f"{i}/{len(cases)}", flush=True)
    print(folder)

