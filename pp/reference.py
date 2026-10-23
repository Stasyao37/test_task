"""Справочные данные: словари свободного текста и правила согласованности полей.

Строятся из разметки train и справочника подразделений; при оценке на train —
только из фолдов, не содержащих оцениваемый документ.
"""
import csv
from dataclasses import dataclass

from .text import build_vocabs

# Год выдачи минус год в серии (по модулю 100): на train всегда 0..3.
SERIES_YEAR_LAG = range(4)


def load_subdivisions(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Reference:
    vocabs: dict    # поле -> text.Vocab
    regions: dict   # первые 2 цифры серии -> первые 2 цифры кода подразделения
    codes: set      # коды подразделений из справочника


def build_reference(label_fields, subdivisions):
    """subdivisions — список строк справочника {code, name}."""
    regions = {f["Licence_number"][:2]: f["Issue_organisation_code"][:2] for f in label_fields}
    return Reference(
        vocabs=build_vocabs(label_fields, [s["name"] for s in subdivisions]),
        regions=regions,
        codes={s["code"] for s in subdivisions},
    )


def consistent(fields, ref):
    """Номер, код и дата выдачи согласованы между собой и со справочниками."""
    number, code, issue = (fields.get(f) for f in
                           ("Licence_number", "Issue_organisation_code", "Issue_date"))
    if not (number and code and issue):
        return False
    return (code in ref.codes
            and ref.regions.get(number[:2]) == code[:2]
            and (int(issue[-2:]) - int(number[3:5])) % 100 in SERIES_YEAR_LAG)
