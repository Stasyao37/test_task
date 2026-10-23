"""Свободный текст: «место рождения» и «кем выдан».

MRZ эти поля не дублирует, поэтому:
  * слова со «слабыми» символами (char_conf < LOW_CONF), которых нет в словаре,
    исправляются на словарное слово на расстоянии 1, если правка приходится ровно
    на слабые символы и кандидат единственный (СБЛАСТИ -> ОБЛАСТИ);
  * считаются признаки надёжности: остаточная минимальная уверенность, доля
    покрытия рамки поля строками (потерянная строка), слова вне словаря и т.п.
"""
from collections import Counter
from dataclasses import dataclass

from rapidfuzz import process
from rapidfuzz.distance import Levenshtein

from .fields import norm

TEXT_FIELDS = ("Birth_place_ru", "Issue_organization_ru")
LOW_CONF = 0.9

# Сокращения, которые в разметке train пишутся только с точкой (0 исключений);
# OCR точку часто теряет с высокой уверенностью.
DOTTED_ABBR = {
    "Birth_place_ru": {"С", "П", "Д", "Г", "Х", "ГОР", "ДЕР", "ПОС", "СТАН", "РЕСП", "ОБЛ", "КР", "Р.П"},
    "Issue_organization_ru": {"Г", "ГОР", "П", "ПОС"},
}


class Vocab:
    """Словарь слов и целых строк поля."""

    def __init__(self, texts):
        texts = [norm(t) for t in texts if t]
        self.words = Counter(w for t in texts for w in t.split())
        self.full = set(texts)
        self._list = list(self.words)

    def __contains__(self, word):
        return word in self.words

    def near(self, word):
        """Словарные слова на расстоянии Левенштейна 1."""
        return [m for m, _, _ in process.extract(word, self._list, scorer=Levenshtein.distance,
                                                 score_cutoff=1, limit=20)]


def build_vocabs(label_fields, subdivision_names=()):
    """label_fields — список словарей полей из разметки."""
    return {
        "Birth_place_ru": Vocab(f["Birth_place_ru"] for f in label_fields),
        "Issue_organization_ru": Vocab([f["Issue_organization_ru"] for f in label_fields]
                                       + list(subdivision_names)),
    }


def _words(field):
    """Слова поля с уверенностями их символов (строки склеиваются через пробел)."""
    out = []
    for line in field["lines"]:
        pos = 0
        for w in line["text"].split(" "):
            if w:
                out.append((w.upper(), line["char_conf"][pos:pos + len(w)]))
            pos += len(w) + 1
    return out


def _fix(word, conf, vocab):
    """Словарная замена слова или None."""
    low = {i for i, c in enumerate(conf) if c < LOW_CONF}
    good = []
    for cand in vocab.near(word):
        ops = Levenshtein.editops(word, cand)
        # вставка «между» символами допустима рядом со слабым символом
        if all(o.src_pos in low or (o.tag == "insert" and o.src_pos - 1 in low) for o in ops):
            good.append(cand)
    return good[0] if len(good) == 1 else None


def _coverage(field):
    """Высота, занятая строками, относительно рамки поля; < ~0.8 — строка потеряна."""
    lines = field["lines"]
    top = min(ln["box"][1] for ln in lines)
    bottom = max(ln["box"][1] + ln["box"][3] for ln in lines)
    return (bottom - top) / field["box"][3] if field["box"][3] else 0.0


@dataclass
class TextResult:
    text: str
    n_fixed: int        # исправлено слов
    n_oov: int          # слов вне словаря после исправления
    n_low: int          # слабых символов в неисправленных словах
    min_conf: float     # минимальная уверенность по неисправленным словам
    coverage: float
    n_lines: int
    known: bool         # строка целиком совпадает с известной


def process_field(field, vocab, abbr=()):
    if not field or not field.get("lines"):
        return None
    out, n_fixed, n_low, confs = [], 0, 0, []
    for word, conf in _words(field):
        fixed = None
        if word in abbr:
            fixed = word + "."
        elif word not in vocab and conf and min(conf) < LOW_CONF:
            fixed = _fix(word, conf, vocab)
        if fixed:
            out.append(fixed)
            n_fixed += 1
        else:
            out.append(word)
            confs.extend(conf)
            n_low += sum(c < LOW_CONF for c in conf)
    text = norm(" ".join(out))
    return TextResult(
        text=text,
        n_fixed=n_fixed,
        n_oov=sum(w not in vocab for w in text.split()),
        n_low=n_low,
        min_conf=min(confs, default=1.0),
        coverage=_coverage(field),
        n_lines=len(field["lines"]),
        known=text in vocab.full,
    )
