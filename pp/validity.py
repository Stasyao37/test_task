"""Действительность паспорта РФ на дату проверки.

Паспорт выдаётся с 14 лет и подлежит замене при достижении 20 и 45 лет.
GRACE_DAYS — отсрочка после 20/45-летия, в течение которой паспорт ещё считается
действительным (90 дней на подачу документов). Трактовку нужно проверить на train.
"""
import datetime as dt

CHECK_DATE = dt.date(2026, 10, 1)
GRACE_DAYS = 0


def parse_date(s):
    try:
        return dt.datetime.strptime(s, "%d.%m.%Y").date()
    except (TypeError, ValueError):
        return None


def birthday(birth, age):
    """День, когда исполняется age лет (для 29.02 в невисокосный год — 01.03)."""
    try:
        return birth.replace(year=birth.year + age)
    except ValueError:
        return dt.date(birth.year + age, 3, 1)


def invalid_reason(birth_date, issue_date, on=CHECK_DATE, grace_days=GRACE_DAYS):
    """None, если паспорт действителен; иначе строка с причиной."""
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
