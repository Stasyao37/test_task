"""python postprocess.py <predictions.jsonl> <answers.jsonl>"""
import json
import sys
from pathlib import Path

from pp.combine import MRZ_FIELDS, NAME_FIELDS, combine
from pp.text import TEXT_FIELDS, build_vocabs, load_subdivisions
from pp.validity import invalid_reason

ROOT = Path(__file__).resolve().parent
LABELS = ROOT / "data" / "train_labels.jsonl"
SUBDIVISIONS = ROOT / "reference" / "subdivisions.csv"

VERIFIED = {"agree", "mrz"}
# поля, которые MRZ дублирует: принимаем только подтверждённые
MRZ_COVERED = (*MRZ_FIELDS, *NAME_FIELDS)
MIN_COVERAGE = 0.82   # ниже — потеряна строка (на train у верных значений не бывает)
# поле -> (мин. уверенность неисправленных символов, макс. число слов вне словаря)
TEXT_RULES = {
    "Issue_organization_ru": (0.95, 0),
    "Birth_place_ru": (0.95, 2),
}


def text_ok(f, r):
    """Свободный текст достаточно надёжен, чтобы его принять."""
    if r is None or r.coverage < MIN_COVERAGE:
        return False
    min_conf, max_oov = TEXT_RULES[f]
    return r.known or (r.min_conf >= min_conf and r.n_oov <= max_oov)


def decide(doc, vocabs):
    """Вернуть (decision, fields) для одного документа."""
    fields, status, texts = combine(doc, vocabs)
    if any(status[f] not in VERIFIED for f in MRZ_COVERED):
        return "reject", None
    if not all(text_ok(f, texts[f]) for f in TEXT_FIELDS):
        return "reject", None
    if invalid_reason(fields["Birth_date"], fields["Issue_date"]):
        return "reject", None
    return "accept", fields


def load_vocabs(labels_path=LABELS, subdivisions_path=SUBDIVISIONS):
    with open(labels_path, encoding="utf-8") as fh:
        labels = [json.loads(line)["fields"] for line in fh]
    return build_vocabs(labels, load_subdivisions(subdivisions_path))


def run(docs, vocabs):
    for doc in docs:
        decision, fields = decide(doc, vocabs)
        ans = {"doc_id": doc["doc_id"], "decision": decision}
        if decision == "accept":
            ans["fields"] = fields
        yield ans


def main(pred_path, out_path):
    vocabs = load_vocabs()
    with open(pred_path, encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for ans in run(map(json.loads, fin), vocabs):
            fout.write(json.dumps(ans, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
