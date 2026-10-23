FIELDS = ["Last_name_ru", "First_name_ru", "Middle_name_ru", "Sex_ru", "Birth_date",
          "Birth_place_ru", "Issue_date", "Issue_organisation_code", "Licence_number",
          "Issue_organization_ru"]


def norm(s):
    # как в evaluate.py
    return " ".join(str(s or "").split()).upper()


def raw_fields(doc):
    out = {}
    for f in FIELDS:
        v = doc["viz"].get(f)
        out[f] = " ".join(line["text"] for line in v["lines"]) if v and v["lines"] else None
    return out
