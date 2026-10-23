"""Разбор машиночитаемой зоны (MRZ) внутреннего паспорта РФ.

Строка 1 (44 символа): PNRUS + ФАМИЛИЯ<<ИМЯ<ОТЧЕСТВО, транслитерация по таблице ниже,
пробелы и дефисы -> '<', поле имён 39 символов (обрезается / добивается '<').

Строка 2 (44 символа):
  [0:9]   серия (3 первые цифры) + номер     [9]  контрольная цифра
  [10:13] RUS
  [13:19] дата рождения ГГММДД               [19] контрольная цифра
  [20]    пол M/F
  [21:28] срок действия + контрольная (не заполняется: '<<<<<<<')
  [28]    4-я цифра серии
  [29:35] дата выдачи ГГММДД
  [35:41] код подразделения без дефиса
  [41]    '<'                                [42] контрольная цифра [28:42]
  [43]    итоговая контрольная цифра
"""
from dataclasses import dataclass, field
from itertools import product

from .validity import parse_date

TRANSLIT = dict(zip("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ- ",
                    "ABVGDEEJZIQKLMNOPRSTUFHC34WXY9678<<"))
NAMES_LEN = 39
LINE_LEN = 44
# Последний год, который в 2026 году может быть годом рождения 14-летнего / годом выдачи.
CURRENT_YY = 26


def check_digit(s):
    """Контрольная цифра ICAO 9303: веса 7-3-1, '<' = 0, A..Z = 10..35."""
    total = 0
    for i, ch in enumerate(s):
        if ch.isdigit():
            v = int(ch)
        elif "A" <= ch <= "Z":
            v = ord(ch) - 55
        else:
            v = 0
        total += v * (7, 3, 1)[i % 3]
    return str(total % 10)


def translit_names(last, first, middle):
    """ФИО кириллицей -> поле имён строки 1 MRZ (39 символов); None, если есть чужие символы."""
    s = f"{last}<<{first}<{middle or ''}"
    out = []
    for ch in s:
        if ch == "<":
            out.append(ch)
        elif ch in TRANSLIT:
            out.append(TRANSLIT[ch])
        else:
            return None
    return "".join(out)[:NAMES_LEN].ljust(NAMES_LEN, "<")


def _date(yymmdd, century_cut):
    """ГГММДД -> ДД.ММ.ГГГГ; годы > century_cut относятся к XX веку."""
    if not yymmdd.isdigit():
        return None
    yy, mm, dd = int(yymmdd[:2]), yymmdd[2:4], yymmdd[4:6]
    year = 1900 + yy if yy > century_cut else 2000 + yy
    v = f"{dd}.{mm}.{year}"
    return v if parse_date(v) else None


def _checks(l2):
    """Контрольные цифры по сегментам строки 2.

    Буква на месте цифры тоже может дать верную контрольную сумму ('O' = 24 и т.п.),
    поэтому сегмент засчитывается, только если он ещё и цифровой.
    """
    return {
        "number": l2[0:10].isdigit() and check_digit(l2[0:9]) == l2[9],
        "birth": l2[13:20].isdigit() and check_digit(l2[13:19]) == l2[19],
        "optional": l2[28:41].isdigit() and l2[42].isdigit() and check_digit(l2[28:42]) == l2[42],
        "final": l2[43].isdigit() and check_digit(l2[0:10] + l2[13:20] + l2[21:43]) == l2[43],
    }


def _repair_line2(text):
    """Строка 2 длиной 43/45: вставить/удалить один символ так, чтобы сошлись все контрольные.

    Возвращает исправленную строку, только если вариант единственный.
    """
    if len(text) == LINE_LEN + 1:
        cands = {text[:i] + text[i + 1:] for i in range(len(text))}
    elif len(text) == LINE_LEN - 1:
        cands = {text[:i] + ch + text[i:] for i, ch in product(range(len(text) + 1), "0123456789<")}
    else:
        return None
    good = [c for c in cands if c[10:13] == "RUS" and all(_checks(c).values())]
    return good[0] if len(good) == 1 else None


@dataclass
class Mrz:
    names: str | None = None            # поле имён строки 1 (39 символов) или None
    checks: dict = field(default_factory=dict)
    licence_number: str | None = None   # "NN NN NNNNNN"
    birth_date: str | None = None       # "ДД.ММ.ГГГГ"
    issue_date: str | None = None
    code: str | None = None             # "NNN-NNN"
    sex: str | None = None              # "МУЖ." / "ЖЕН."
    repaired: bool = False              # строка 2 восстановлена по контрольным цифрам
    line2: str | None = None

    def ok(self, *names):
        return bool(self.checks) and all(self.checks.get(n) for n in names)


def _yymmdd(d):
    return d[8:10] + d[3:5] + d[:2]


def confirms(m, number, birth, sex, issue, code):
    """Значения viz, подставленные в строку 2 вместо прочитанных, дают верными ВСЕ
    контрольные цифры (прочитанные из MRZ). Две независимые проверки на каждое поле —
    случайное совпадение маловероятно (на train 105/105 верно)."""
    if m is None or m.line2 is None or not all((number, birth, sex, issue, code)):
        return False
    l2, s = m.line2, number.replace(" ", "")
    new = (s[:3] + s[4:] + l2[9] + "RUS" + _yymmdd(birth) + l2[19]
           + {"МУЖ.": "M", "ЖЕН.": "F"}[sex] + l2[21:28]
           + s[3] + _yymmdd(issue) + code.replace("-", "") + "<" + l2[42:44])
    return all(_checks(new).values())


def parse(doc):
    """Разобрать MRZ документа; None, если MRZ нет."""
    m = doc.get("mrz")
    if not m or not m.get("lines"):
        return None
    lines = [ln["text"] for ln in m["lines"]]
    res = Mrz()

    l1 = lines[0]
    if l1.startswith("PNRUS") and len(l1) >= LINE_LEN - 1:
        res.names = l1[5:5 + NAMES_LEN].ljust(NAMES_LEN, "<")

    if len(lines) < 2:
        return res
    l2 = lines[1]
    if len(l2) != LINE_LEN:
        l2 = _repair_line2(l2)
        if l2 is None:
            return res
        res.repaired = True
    if l2[10:13] != "RUS":
        return res

    res.line2 = l2
    res.checks = _checks(l2)
    s = l2[0:3] + l2[28] + l2[3:9]
    if s.isdigit():
        res.licence_number = f"{s[:2]} {s[2:4]} {s[4:]}"
    res.birth_date = _date(l2[13:19], CURRENT_YY)
    res.issue_date = _date(l2[29:35], CURRENT_YY)
    if l2[35:41].isdigit():
        res.code = f"{l2[35:38]}-{l2[38:41]}"
    res.sex = {"M": "МУЖ.", "F": "ЖЕН."}.get(l2[20])
    return res
