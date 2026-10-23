"""Словари и правила согласованности из разметки train и справочника подразделений."""
import csv
from dataclasses import dataclass

from .text import build_vocabs

# год выдачи - год в серии
SERIES_YEAR_LAG = range(4)


def load_subdivisions(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Reference:
    vocabs: dict
    regions: dict   # регион серии -> регион кода подразделения
    codes: set


def build_reference(label_fields, subdivisions):
    regions = {f["Licence_number"][:2]: f["Issue_organisation_code"][:2] for f in label_fields}
    return Reference(
        vocabs=build_vocabs(label_fields, [s["name"] for s in subdivisions]),
        regions=regions,
        codes={s["code"] for s in subdivisions},
    )


def consistent(fields, ref):
    number, code, issue = (fields.get(f) for f in
                           ("Licence_number", "Issue_organisation_code", "Issue_date"))
    if not (number and code and issue):
        return False
    return (code in ref.codes
            and ref.regions.get(number[:2]) == code[:2]
            and (int(issue[-2:]) - int(number[3:5])) % 100 in SERIES_YEAR_LAG)
