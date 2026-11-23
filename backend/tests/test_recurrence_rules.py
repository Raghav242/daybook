from datetime import date, timedelta

import pytest

from app.modules.recurrence.rules import MAX_PER_PASS, Rule, nth_date, occurrences


def brute_force(rule, first, last):
    days, n = [], 0
    while True:
        day = nth_date(rule, n)
        if day > last or (rule.until_date and day > rule.until_date):
            return days
        if day >= first:
            days.append(day)
        n += 1


def test_month_end_anchor_clamps_without_drifting():
    rule = Rule("monthly", 1, date(2026, 1, 31))
    assert occurrences(rule, date(2026, 1, 1), date(2026, 6, 30)) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
        date(2026, 5, 31),
        date(2026, 6, 30),
    ]


def test_leap_years_and_the_29th():
    rule = Rule("monthly", 12, date(2024, 2, 29))
    assert occurrences(rule, date(2024, 1, 1), date(2028, 12, 31)) == [
        date(2024, 2, 29),
        date(2025, 2, 28),
        date(2026, 2, 28),
        date(2027, 2, 28),
        date(2028, 2, 29),
    ]


def test_monthly_interval_crosses_years():
    rule = Rule("monthly", 5, date(2026, 10, 30))
    assert occurrences(rule, date(2026, 1, 1), date(2027, 12, 31)) == [
        date(2026, 10, 30),
        date(2027, 3, 30),
        date(2027, 8, 30),
    ]


def test_weekly_keeps_weekday_and_interval():
    rule = Rule("weekly", 2, date(2026, 11, 2))  # a Monday
    days = occurrences(rule, date(2026, 11, 1), date(2026, 12, 31))
    assert days == [date(2026, 11, 2) + timedelta(weeks=2 * i) for i in range(5)]
    assert {day.weekday() for day in days} == {0}


def test_range_boundaries_are_inclusive_and_until_date_stops():
    rule = Rule("daily", 1, date(2026, 11, 1), until_date=date(2026, 11, 5))
    assert occurrences(rule, date(2026, 11, 3), date(2026, 11, 30)) == [
        date(2026, 11, 3),
        date(2026, 11, 4),
        date(2026, 11, 5),
    ]
    assert occurrences(rule, date(2026, 11, 6), date(2026, 11, 30)) == []
    assert occurrences(rule, date(2026, 10, 1), date(2026, 10, 31)) == []


@pytest.mark.parametrize(
    "rule",
    [
        Rule("daily", 3, date(2025, 12, 30)),
        Rule("weekly", 3, date(2025, 1, 4)),
        Rule("monthly", 1, date(2025, 1, 31)),
        Rule("monthly", 7, date(2024, 8, 31)),
    ],
)
def test_skip_ahead_matches_brute_force(rule):
    for offset in range(0, 500, 37):
        first = date(2026, 1, 1) + timedelta(days=offset)
        last = first + timedelta(days=90)
        assert occurrences(rule, first, last) == brute_force(rule, first, last)


def test_generation_pass_is_bounded_and_does_not_overflow():
    rule = Rule("daily", 1, date(2020, 1, 1))
    assert len(occurrences(rule, date(2020, 1, 1), date(2030, 1, 1))) == MAX_PER_PASS
    late = Rule("monthly", 1, date(9999, 11, 30))
    assert occurrences(late, date(9999, 1, 1), date.max) == [date(9999, 11, 30), date(9999, 12, 30)]
