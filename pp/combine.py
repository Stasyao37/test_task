"""Сведение viz и MRZ по полям.

Статусы: agree / mrz — подтверждено MRZ с верной контрольной цифрой; raw — viz совпал с MRZ
без неё; sum — viz сходится с контрольными цифрами MRZ; fixed — ФИО исправлены по MRZ;
checked — согласовано со справочниками; sex — по отчеству; viz — без подтверждения.
"""
from . import mrz as mrz_mod
from . import names as names_mod
from . import normalize as N
from .fields import FIELDS, raw_fields
from .reference import consistent
from .text import DOTTED_ABBR, TEXT_FIELDS, process_field

NAME_FIELDS = ("Last_name_ru", "First_name_ru", "Middle_name_ru")

# поле -> (нормализатор, атрибут Mrz, контрольные цифры)
MRZ_FIELDS = {
    "Licence_number": (N.licence_number, "licence_number", ("number", "optional")),
    "Birth_date": (N.birth_date, "birth_date", ("birth",)),
    "Issue_date": (N.issue_date, "issue_date", ("optional",)),
    "Issue_organisation_code": (N.code, "code", ("optional",)),
    "Sex_ru": (N.sex, "sex", ("final",)),
}


def _name(s):
    # в разметке ФИО Ё почти не встречается, OCR её путает с Е
    return None if s is None else N.text(s).replace("Ё", "Е")


# дату рождения без MRZ проверить нечем
CHECKED_MIN_CONF = {
    "Issue_organisation_code": 0.9,
    "Licence_number": 0.98,
    "Issue_date": 0.98,
}

MALE_ENDINGS = ("ВИЧ", "ОГЛЫ", "УУЛУ")
FEMALE_ENDINGS = ("ВНА", "КЫЗЫ", "ГЫЗЫ")


def _merge(viz_value, mrz_value, mrz_ok):
    if mrz_ok and mrz_value is not None:
        return mrz_value, "agree" if viz_value == mrz_value else "mrz"
    if viz_value is not None and viz_value == mrz_value:
        return viz_value, "raw"
    if viz_value is not None:
        return viz_value, "viz"
    return None, "missing"


def _sex_by_middle(middle):
    if middle and middle.endswith(MALE_ENDINGS):
        return "МУЖ."
    if middle and middle.endswith(FEMALE_ENDINGS):
        return "ЖЕН."
    return None


def _names(doc, raw, m):
    fixed = names_mod.resolve(doc)
    if fixed is not None:
        same = all(fixed[f] == _name(raw[f] or "") for f in NAME_FIELDS)
        return fixed, "agree" if same else "fixed"
    last, first, middle = (_name(raw[f]) for f in NAME_FIELDS)
    if last is None or first is None:
        status = "missing"
    elif m is not None and m.names is not None and \
            mrz_mod.translit_names(last, first, middle or "") == m.names:
        middle = middle or ""
        status = "agree"
    else:
        status = "viz" if middle is not None else "missing"
    return {"Last_name_ru": last, "First_name_ru": first, "Middle_name_ru": middle}, status


def _min_conf(field):
    return min((c for ln in field["lines"] for c in ln["char_conf"]), default=0.0) if field else 0.0


def combine(doc, ref):
    raw = raw_fields(doc)
    m = mrz_mod.parse(doc)
    fields, status = {}, {}

    for f, (norm_fn, attr, checks) in MRZ_FIELDS.items():
        mrz_value = getattr(m, attr) if m else None
        fields[f], status[f] = _merge(norm_fn(raw[f]), mrz_value, m is not None and m.ok(*checks))

    if mrz_mod.confirms(m, number=fields["Licence_number"], birth=fields["Birth_date"],
                        sex=fields["Sex_ru"], issue=fields["Issue_date"],
                        code=fields["Issue_organisation_code"]):
        for f in MRZ_FIELDS:
            if status[f] == "viz":
                status[f] = "sum"

    names, names_status = _names(doc, raw, m)
    fields.update(names)
    status.update(dict.fromkeys(NAME_FIELDS, names_status))
    if any(status[f] == "viz" for f in CHECKED_MIN_CONF) and consistent(fields, ref):
        for f, min_conf in CHECKED_MIN_CONF.items():
            if status[f] == "viz" and _min_conf(doc["viz"].get(f)) >= min_conf:
                status[f] = "checked"
    if status["Sex_ru"] == "viz" and fields["Sex_ru"] == _sex_by_middle(fields["Middle_name_ru"]):
        status["Sex_ru"] = "sex"

    texts = {}
    for f in TEXT_FIELDS:
        texts[f] = process_field(doc["viz"].get(f), ref.vocabs[f], DOTTED_ABBR[f])
        fields[f] = texts[f].text if texts[f] else None
        status[f] = "viz" if fields[f] is not None else "missing"

    return {f: fields[f] for f in FIELDS}, {f: status[f] for f in FIELDS}, texts
