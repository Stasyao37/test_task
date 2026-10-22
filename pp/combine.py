"""Сведение visual-зоны и MRZ: итоговые значения полей и источник каждого.

Статусы поля:
  agree   — viz совпало с MRZ, контрольные цифры MRZ сошлись (на train 100% верно)
  mrz     — значение взято из MRZ с верными контрольными цифрами, viz не совпало/не читается
  viz     — подтверждения нет, значение только из viz
  missing — значения нет
"""
from . import mrz as mrz_mod
from . import normalize as N
from .fields import FIELDS, raw_fields
from .text import DOTTED_ABBR, TEXT_FIELDS, process_field

NAME_FIELDS = ("Last_name_ru", "First_name_ru", "Middle_name_ru")

# поле -> (нормализатор viz, атрибут Mrz, контрольные цифры, покрывающие поле)
MRZ_FIELDS = {
    "Licence_number": (N.licence_number, "licence_number", ("number", "optional")),
    "Birth_date": (N.date, "birth_date", ("birth",)),
    "Issue_date": (N.date, "issue_date", ("optional",)),
    "Issue_organisation_code": (N.code, "code", ("optional",)),
    "Sex_ru": (N.sex, "sex", ("final",)),
}


def _name(s):
    # OCR путает Е/Ё, в разметке ФИО буквы Ё практически нет, в MRZ обе -> E
    return None if s is None else N.text(s).replace("Ё", "Е")


def _merge(viz_value, mrz_value, mrz_ok):
    if mrz_ok and mrz_value is not None:
        return mrz_value, "agree" if viz_value == mrz_value else "mrz"
    if viz_value is not None:
        return viz_value, "viz"
    return None, "missing"


def _names(raw, m):
    last, first, middle = (_name(raw[f]) for f in NAME_FIELDS)
    if last is None or first is None:
        status = "missing"
    elif m is not None and m.names is not None and \
            mrz_mod.translit_names(last, first, middle or "") == m.names:
        # MRZ подтверждает и пустое отчество, если детектор его не нашёл
        middle = middle or ""
        status = "agree"
    else:
        status = "viz" if middle is not None else "missing"
    return {"Last_name_ru": last, "First_name_ru": first, "Middle_name_ru": middle}, status


def combine(doc, vocabs):
    """-> (fields, status, texts): значения 10 полей, статус каждого и разбор свободного текста."""
    raw = raw_fields(doc)
    m = mrz_mod.parse(doc)
    fields, status = {}, {}

    for f, (norm_fn, attr, checks) in MRZ_FIELDS.items():
        mrz_value = getattr(m, attr) if m else None
        fields[f], status[f] = _merge(norm_fn(raw[f]), mrz_value, m is not None and m.ok(*checks))

    names, names_status = _names(raw, m)
    fields.update(names)
    status.update(dict.fromkeys(NAME_FIELDS, names_status))

    texts = {}
    for f in TEXT_FIELDS:
        texts[f] = process_field(doc["viz"].get(f), vocabs[f], DOTTED_ABBR[f])
        fields[f] = texts[f].text if texts[f] else None
        status[f] = "viz" if fields[f] is not None else "missing"

    return {f: fields[f] for f in FIELDS}, {f: status[f] for f in FIELDS}, texts
