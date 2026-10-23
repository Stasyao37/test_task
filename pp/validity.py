"""Действительность паспорта: выдан с 14 лет, замена в 20 и 45."""
import datetime as dt

CHECK_DATE = dt.date(2026, 10, 1)
GRACE_DAYS = 0   # 90-дневную отсрочку на замену не учитываем


def parse_date(s):
    try:
        return dt.datetime.strptime(s, "%d.%m.%Y").date()
    except (TypeError, ValueError):
        return None


def birthday(birth, age):
    try:
        return birth.replace(year=birth.year + age)
    except ValueError:
        return dt.date(birth.year + age, 3, 1)


def invalid_reason(birth_date, issue_date, on=CHECK_DATE, grace_days=GRACE_DAYS):
    b, i = parse_date(birth_date), parse_date(issue_date)
    if b is None or i is None:
        return "bad_date"
    if i > on:
        return "issued_in_future"
    if i < birthday(b, 14):
        return "issued_before_14"
    for age in (20, 45):
        if i < birthday(b, age) and birthday(b, age) + dt.timedelta(days=grace_days) <= on:
            return f"not_replaced_at_{age}"
    return None
