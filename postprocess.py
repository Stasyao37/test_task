"""python postprocess.py <predictions.jsonl> <answers.jsonl>"""
import json
import sys

from pp.combine import MRZ_FIELDS, NAME_FIELDS, combine
from pp.validity import invalid_reason

VERIFIED = {"agree", "mrz"}
# поля, которые MRZ дублирует: принимаем только подтверждённые
MRZ_COVERED = (*MRZ_FIELDS, *NAME_FIELDS)


def decide(doc):
    """Вернуть (decision, fields) для одного документа."""
    fields, status = combine(doc)
    if any(status[f] not in VERIFIED for f in MRZ_COVERED):
        return "reject", None
    if any(v is None for v in fields.values()):
        return "reject", None
    if invalid_reason(fields["Birth_date"], fields["Issue_date"]):
        return "reject", None
    return "accept", fields


def main(pred_path, out_path):
    with open(pred_path, encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for doc in map(json.loads, fin):
            decision, fields = decide(doc)
            ans = {"doc_id": doc["doc_id"], "decision": decision}
            if decision == "accept":
                ans["fields"] = fields
            fout.write(json.dumps(ans, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
