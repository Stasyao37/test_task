"""Сведение visual-зоны и MRZ: итоговые значения полей и источник каждого.

Статусы поля:
  agree   — viz совпало с MRZ, контрольные цифры MRZ сошлись (на train 100% верно)
  mrz     — значение взято из MRZ с верными контрольными цифрами, viz не совпало/не читается
  raw     — viz совпало с MRZ, хотя контрольная цифра не сошлась (два независимых прочтения;
            на train 236/236 верно)
  fixed   — ФИО: расхождения с MRZ решены посимвольно по уверенности (pp/names.py)
  sex     — пол только из viz, но согласуется с окончанием отчества
  sum     — значения viz, подставленные в MRZ, сходятся со всеми её контрольными цифрами
  checked — номер / код / дата выдачи только из viz, но уверенно прочитаны и согласованы
            между собой и со справочниками (pp/reference.py)
  viz     — подтверждения нет, значение только из viz
  missing — значения нет
"""
from . import mrz as mrz_mod
from . import names as names_mod
from . import normalize as N
from .fields import FIELDS, raw_fields
from .reference import consistent
from .text import DOTTED_ABBR, TEXT_FIELDS, process_field

NAME_FIELDS = ("Last_name_ru", "First_name_ru", "Middle_name_ru")

# поле -> (нормализатор viz, атрибут Mrz, контрольные цифры, покрывающие поле)
MRZ_FIELDS = {
    "Licence_number": (N.licence_number, "licence_number", ("number", "optional")),
    "Birth_date": (N.birth_date, "birth_date", ("birth",)),
    "Issue_date": (N.issue_date, "issue_date", ("optional",)),
    "Issue_organisation_code": (N.code, "code", ("optional",)),
    "Sex_ru": (N.sex, "sex", ("final",)),
}


def _name(s):
    # OCR путает Е/Ё, в разметке ФИО буквы Ё практически нет, в MRZ обе -> E
    return None if s is None else N.text(s).replace("Ё", "Е")


# Минимальная уверенность символов поля, при которой значение только из viz можно принять,
# если оно согласовано с остальными (дату рождения проверить нечем — не принимаем).
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
        # MRZ подтверждает и пустое отчество, если детектор его не нашёл
        middle = middle or ""
        status = "agree"
    else:
        status = "viz" if middle is not None else "missing"
    return {"Last_name_ru": last, "First_name_ru": first, "Middle_name_ru": middle}, status


def _min_conf(field):
    return min((c for ln in field["lines"] for c in ln["char_conf"]), default=0.0) if field else 0.0


def combine(doc, ref):
    """-> (fields, status, texts): значения 10 полей, статус каждого и разбор свободного текста."""
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
