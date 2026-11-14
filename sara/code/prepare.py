from pathlib import Path
import hashlib
import json
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data/public"
PRIVATE = ROOT / "data/evaluator"
ARCHIVE = PRIVATE / "sara-v1.tar.gz"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
    temp.replace(path)


def prepare():
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != "e4f1b845016fc38b95b702bbbb27a5c9af3eadfa856ba585662b8b2cd71c187c":
        raise ValueError("Pacote diferente da versão verificada")
    gold = {}
    pairs = set()
    with tarfile.open(ARCHIVE) as archive:
        def read(name):
            return archive.extractfile("sara/" + name).read().decode("utf8")
        statutes = [item.name for item in archive if item.isfile()
                    and item.name.startswith("sara/statutes/source/section")]
        laws = "\n\n".join(read(name[5:]).strip() for name in sorted(statutes))
        if not laws:
            raise ValueError("Legislação ausente")
        write(PUBLIC / "statutes.json", laws)
        for split, count in [("train", 176), ("test", 100)]:
            cases = []
            for name in read("splits/" + split).splitlines():
                if not name.startswith("s"):
                    continue
                body = read("cases/" + name + ".pl")
                narrative, question = body.split("% Text", 1)[1].split("% Question", 1)
                def comments(block):
                    return " ".join(line.strip()[1:].strip() for line in block.splitlines()
                                    if line.strip().startswith("%"))
                text = comments(narrative)
                hypothesis, label = comments(question.split("% Facts", 1)[0]).rsplit(None, 1)
                key = digest(name)
                pair, sign = name.rsplit("_", 1)
                if label != {"pos":"Entailment","neg":"Contradiction"}[sign] or key in gold:
                    raise ValueError(name)
                gold[key] = dict(name=name, label=sign == "pos", pair=pair)
                cases.append(dict(id=key, text=text, hypothesis=hypothesis))
            groups = {gold[c["id"]]["pair"] for c in cases}
            if len(cases) != count or len(groups)*2 != count or pairs & groups:
                raise ValueError(split)
            pairs.update(groups)
            cases.sort(key=lambda c: (digest(gold[c["id"]]["pair"]), c["id"]))
            write(PUBLIC / (split + ".json"), cases)
            if split == "train":
                write(PUBLIC / "pilot.json", cases[:20])
    write(PRIVATE / "gold.json", gold)
    print("176 treino, 100 teste, 20 piloto")


if __name__ == "__main__":
    prepare()
