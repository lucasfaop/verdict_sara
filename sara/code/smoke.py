"""Verificação offline do fluxo original e contrafactual."""
from run import COMPILE, DIRECT, EDIT, trial, load, PUBLIC
from oracle import parts
from prepare import ARCHIVE
import tarfile


class Fixture:
    def ask(self, prompt, ctx):
        if prompt == COMPILE:
            assert "text" not in ctx
            return dict(variables={"v1":{"type":"Real","meaning":"age"}}, rule=[">=", "v1", 18])
        adult = "20" in ctx["text"]
        age = 20 if adult else 17
        if prompt == DIRECT:
            return dict(decision=adult, old=str(age), new="17" if adult else "20")
        if prompt == EDIT:
            assert ctx["pivotal"] == ["v1"]
            return dict(old="20", new="17")
        return dict(facts={"v1":dict(value=age,quote=str(age))})


r = trial(Fixture(), dict(statutes="Adults are aged 18 or older.", hypothesis="Alex is an adult.", text="Alex is 20."))
for arm in ("direct","verdict"):
    assert r["originals"][arm]["decision"] is True
    for other in ("direct","verdict"):
        assert r["edits"][arm]["predictions"][other]["decision"] is False
with tarfile.open(ARCHIVE) as archive:
    for member in archive:
        if member.name.startswith("sara/cases/s") and member.name.endswith(".pl"):
            facts, query = parts(archive.extractfile(member).read().decode())
            assert facts.strip() and query.strip()
for split, n in [("train",176),("test",100),("pilot",20)]:
    rows = load(PUBLIC / (split + ".json"))
    assert len(rows) == n and all(set(row) == {"id","text","hypothesis"} for row in rows)
print("OK: corpus oficial, consultas e intervenções dos dois braços")
