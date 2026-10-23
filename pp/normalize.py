"""Приведение распознанных значений к формату разметки.

Возвращает None, если значение не удаётся привести к формату без угадывания
(лишняя/пропущенная цифра и т.п.) — такие поля восстанавливаются из MRZ или документ
отклоняется.
"""
import re

from .validity import parse_date

# Кириллица/латиница, которую OCR путает с цифрами в цифровых полях.
DIGIT_LOOKALIKES = str.maketrans({"О": "0", "O": "0", "З": "3", "Б": "6", "б": "6"})
SEXES = ("МУЖ.", "ЖЕН.")


def _digits(s, n):
    """Ровно n цифр из строки (после замены похожих букв) или None."""
    d = re.sub(r"\D", "", s.translate(DIGIT_LOOKALIKES))
    return d if len(d) == n else None


BIRTH_YEARS = range(1900, 2013)   # в 2026 году паспорт есть только у родившихся до 2012
ISSUE_YEARS = range(1997, 2027)   # паспорт РФ нового образца выдаётся с 1997 года


def date(s, years=None):
    if s is None:
        return None
    d = _digits(s, 8)
    if d is None:
        return None
    v = f"{d[:2]}.{d[2:4]}.{d[4:]}"
    if not parse_date(v) or (years is not None and int(d[4:]) not in years):
        return None
    return v


def birth_date(s):
    return date(s, BIRTH_YEARS)


def issue_date(s):
    return date(s, ISSUE_YEARS)


def code(s):
    if s is None:
        return None
    d = _digits(s, 6)
    return f"{d[:3]}-{d[3:]}" if d else None


def licence_number(s):
    if s is None:
        return None
    d = _digits(s, 10)
    return f"{d[:2]} {d[2:4]} {d[4:]}" if d else None


def sex(s):
    """МУЖ./ЖЕН.; допускаем одну ошибку OCR (МЧЖ., ЖЕИ.), т.к. варианта всего два."""
    if s is None:
        return None
    s = s.strip().upper()
    if s in SEXES:
        return s
    t = s.rstrip(".")
    hits = [v for v in SEXES if len(t) == 3 and sum(a != b for a, b in zip(t, v[:3])) <= 1]
    return hits[0] if len(hits) == 1 else None


def text(s):
    """Свободный текст: схлопнуть пробелы, верхний регистр."""
    return None if s is None else " ".join(s.split()).upper()
