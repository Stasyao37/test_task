"""Место рождения и кем выдан: словарное исправление слабых символов и признаки надёжности."""
from collections import Counter
from dataclasses import dataclass

from rapidfuzz import process
from rapidfuzz.distance import Levenshtein

from .fields import norm

TEXT_FIELDS = ("Birth_place_ru", "Issue_organization_ru")
LOW_CONF = 0.9

# в разметке всегда с точкой, OCR её теряет
DOTTED_ABBR = {
    "Birth_place_ru": {"С", "П", "Д", "Г", "Х", "ГОР", "ДЕР", "ПОС", "СТАН", "РЕСП", "ОБЛ", "КР", "Р.П"},
    "Issue_organization_ru": {"Г", "ГОР", "П", "ПОС"},
}


class Vocab:
    def __init__(self, texts):
        texts = [norm(t) for t in texts if t]
        self.words = Counter(w for t in texts for w in t.split())
        self.full = set(texts)
        self._list = list(self.words)

    def __contains__(self, word):
        return word in self.words

    def near(self, word):
        return [m for m, _, _ in process.extract(word, self._list, scorer=Levenshtein.distance,
                                                 score_cutoff=1, limit=20)]


def build_vocabs(label_fields, subdivision_names=()):
    return {
        "Birth_place_ru": Vocab(f["Birth_place_ru"] for f in label_fields),
        "Issue_organization_ru": Vocab([f["Issue_organization_ru"] for f in label_fields]
                                       + list(subdivision_names)),
    }


def _words(field):
    out = []
    for line in field["lines"]:
        pos = 0
        for w in line["text"].split(" "):
            if w:
                out.append((w.upper(), line["char_conf"][pos:pos + len(w)]))
            pos += len(w) + 1
    return out


def _fix(word, conf, vocab):
    low = {i for i, c in enumerate(conf) if c < LOW_CONF}
    good = []
    for cand in vocab.near(word):
        ops = Levenshtein.editops(word, cand)
        if all(o.src_pos in low or (o.tag == "insert" and o.src_pos - 1 in low) for o in ops):
            good.append(cand)
    return good[0] if len(good) == 1 else None


def _coverage(field):
    lines = field["lines"]
    top = min(ln["box"][1] for ln in lines)
    bottom = max(ln["box"][1] + ln["box"][3] for ln in lines)
    return (bottom - top) / field["box"][3] if field["box"][3] else 0.0


@dataclass
class TextResult:
    text: str
    n_fixed: int
    n_oov: int
    n_low: int
    min_conf: float     # по неисправленным словам
    coverage: float
    n_lines: int
    known: bool


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
