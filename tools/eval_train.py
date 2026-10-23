"""Оценка на train с учётом действительности паспорта и разбивкой по source.

python tools/eval_train.py              — кросс-валидация: словари свободного текста строятся
                                          без оцениваемого фолда, ответы -> answers_train.jsonl
python tools/eval_train.py answers.jsonl — оценить готовый файл ответов
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import postprocess  # noqa: E402
from pp.fields import FIELDS, norm  # noqa: E402
from pp.reference import build_reference, load_subdivisions  # noqa: E402
from pp.validity import invalid_reason  # noqa: E402

N_FOLDS = 5


def load(path):
    with open(path, encoding="utf-8") as fh:
        return {d["doc_id"]: d for d in map(json.loads, fh)}


def cross_val_answers(gt, pred, out_path):
    """Ответы по фолдам: справочные данные из разметки остальных фолдов + справочник."""
    subdivisions = load_subdivisions(postprocess.SUBDIVISIONS)
    ids = sorted(pred)
    ans = {}
    for k in range(N_FOLDS):
        fold = ids[k::N_FOLDS]
        held = set(fold)
        ref = build_reference([g["fields"] for i, g in gt.items() if i not in held], subdivisions)
        for a in postprocess.run((pred[i] for i in fold), ref):
            ans[a["doc_id"]] = a
    with open(out_path, "w", encoding="utf-8") as fh:
        for i in ids:
            fh.write(json.dumps(ans[i], ensure_ascii=False) + "\n")
    return ans


def main(ans_path=None, gt_path="data/train_labels.jsonl", pred_path="data/train_predictions.jsonl"):
    gt, pred = load(gt_path), load(pred_path)
    ans = load(ans_path) if ans_path else cross_val_answers(gt, pred, "answers_train.jsonl")
    missing = set(gt) - set(ans)
    if missing:
        sys.exit(f"нет ответа для {len(missing)} документов, например {sorted(missing)[:3]}")

    by_src = defaultdict(Counter)
    field_errors, invalid = Counter(), Counter()
    for doc_id, g in gt.items():
        gf = g["fields"]
        src = pred[doc_id]["source"]
        reason = invalid_reason(gf["Birth_date"], gf["Issue_date"])
        by_src[src]["n"] += 1
        by_src[src]["valid"] += reason is None
        a = ans[doc_id]
        if a.get("decision") != "accept":
            continue
        af = a.get("fields") or {}
        wrong = [f for f in FIELDS if norm(af.get(f)) != norm(gf[f])]
        field_errors.update(wrong)
        if reason and not wrong:
            invalid[reason] += 1
        by_src[src]["good" if not wrong and not reason else "bad"] += 1

    total = sum(by_src.values(), Counter())
    print(f"{'source':<10} {'docs':>5} {'valid':>6} {'good':>6} {'bad':>5} {'accept%':>8}")
    for src, c in sorted(by_src.items()) + [("ВСЕГО", total)]:
        print(f"{src:<10} {c['n']:>5} {c['valid']:>6} {c['good']:>6} {c['bad']:>5} "
              f"{c['good'] / c['n']:>8.1%}")
    print("ошибки по полям:  " + (", ".join(f"{f}={c}" for f, c in field_errors.most_common()) or "-"))
    print("приняты недействительные (поля верны): "
          + (", ".join(f"{r}={c}" for r, c in invalid.items()) or "-"))


if __name__ == "__main__":
    main(*sys.argv[1:])
