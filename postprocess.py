"""python postprocess.py <predictions.jsonl> <answers.jsonl>"""
import json
import sys

from pp.fields import raw_fields
from pp.validity import invalid_reason


def decide(doc):
    """Вернуть (decision, fields) для одного документа."""
    fields = raw_fields(doc)
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
