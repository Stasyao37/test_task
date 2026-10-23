"""Сверка ФИО visual-зоны с MRZ посимвольно.

Транслитерация в MRZ — буква в букву (Е/Ё -> E, пробел/дефис -> '<'), поэтому
расхождения viz и MRZ выравниваются по Левенштейну, и каждое решается в пользу
уверенно прочитанной стороны: слабый символ (char_conf < WEAK) против сильного
(>= STRONG). Если решить нельзя — None, документ отклоняется.
"""
from rapidfuzz.distance import Levenshtein

from .mrz import LINE_LEN, NAMES_LEN, TRANSLIT

NAME_FIELDS = ("Last_name_ru", "First_name_ru", "Middle_name_ru")
FROM_LATIN = {lat: cyr for cyr, lat in TRANSLIT.items() if cyr not in "Ё -"}
WEAK = 0.9
STRONG = 0.9
MAX_EDITS = 2


def _viz_chars(doc):
    """[(поле, буква, уверенность)] в порядке поля имён MRZ; None, если разобрать нельзя."""
    out = []
    for j, f in enumerate(NAME_FIELDS):
        out += [(None, "<", 1.0)] * (0, 2, 1)[j]
        v = doc["viz"].get(f)
        if v is None and f == "Middle_name_ru":
            continue
        if v is None or len(v["lines"]) != 1:
            return None
        line = v["lines"][0]
        for ch, c in zip(line["text"].upper().replace("Ё", "Е"), line["char_conf"]):
            if ch not in TRANSLIT:
                return None
            out.append((f, ch, c))
    return out


def resolve(doc):
    """ФИО, согласованные с MRZ (с исправлениями), или None."""
    m = doc.get("mrz")
    if not m or not m["lines"]:
        return None
    l1 = m["lines"][0]
    if len(l1["text"]) != LINE_LEN or not l1["text"].startswith("PNRUS"):
        return None
    viz = _viz_chars(doc)
    if viz is None or len(viz) >= NAMES_LEN:   # длинные ФИО в MRZ обрезаны
        return None

    src = "".join(TRANSLIT.get(ch, ch) for _, ch, _ in viz)
    mrz_text = l1["text"][5:].rstrip("<")
    mrz_conf = l1["char_conf"][5:]
    ops = Levenshtein.editops(src, mrz_text)
    if len(ops) > MAX_EDITS:
        return None

    out = [list(x) for x in viz]
    inserts = []
    for op in ops:
        i, k = op.src_pos, op.dest_pos
        if op.tag == "replace":
            f, ch, c = viz[i]
            lat = mrz_text[k]
            if f is None or lat not in FROM_LATIN:
                return None
            if c < WEAK and mrz_conf[k] >= STRONG:
                out[i][1] = FROM_LATIN[lat]
            elif not (c >= STRONG and mrz_conf[k] < WEAK):
                return None
        elif op.tag == "delete":           # лишняя буква в viz или пропуск в MRZ
            f, _, c = viz[i]
            if f is None:
                return None
            # уверенные задвоения букв в viz встречаются, поэтому «пропуск в MRZ»
            # не принимаем: удаляем только слабую букву viz
            if c >= WEAK:
                return None
            out[i][0] = None
        else:                              # insert: в MRZ буква, которой нет в viz
            lat = mrz_text[k]
            if mrz_conf[k] < WEAK:
                continue                   # мусор в MRZ, viz прав
            near = [viz[j][2] for j in (i - 1, i) if 0 <= j < len(viz) and viz[j][0]]
            if lat not in FROM_LATIN or not near or min(near) >= WEAK:
                return None
            # вставляем в поле соседней слева буквы (или справа в начале поля)
            owner = viz[i - 1][0] if i > 0 and viz[i - 1][0] else (viz[i][0] if i < len(viz) else None)
            if owner is None:
                return None
            inserts.append((i, owner, FROM_LATIN[lat]))

    for i, owner, ch in sorted(inserts, reverse=True):
        out.insert(i, [owner, ch, 1.0])
    names = dict.fromkeys(NAME_FIELDS, "")
    for f, ch, _ in out:
        if f:
            names[f] += ch
    return names
