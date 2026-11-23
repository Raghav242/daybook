"""Pure recurrence rules for date-based tasks and bills.

Occurrences are calendar dates, never instants. "Today" is computed by callers in the
account's profile timezone, so changing the timezone never shifts a scheduled date.

Monthly rules always derive each date from the series start date, not from the previous
occurrence. A series anchored on the 31st falls on the last day of shorter months
(Jan 31, Feb 28/29, Mar 31, Apr 30, ...) and returns to the 31st whenever it exists.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Frequency = Literal["daily", "weekly", "monthly"]
FREQUENCIES = ("daily", "weekly", "monthly")
# Occurrences are materialized this far ahead of the profile's local date.
HORIZON_DAYS = 42
# A safety bound for one generation pass (for example, after a long absence).
MAX_PER_PASS = 400


@dataclass(frozen=True)
class Rule:
    frequency: Frequency
    interval: int
    start_date: date
    until_date: date | None = None


def nth_date(rule: Rule, n: int) -> date:
    """The n-th scheduled date (0 is the start date)."""
    if rule.frequency == "daily":
        return rule.start_date + timedelta(days=n * rule.interval)
    if rule.frequency == "weekly":
        return rule.start_date + timedelta(weeks=n * rule.interval)
    months = rule.start_date.month - 1 + n * rule.interval
    year, month = rule.start_date.year + months // 12, months % 12 + 1
    return date(year, month, min(rule.start_date.day, monthrange(year, month)[1]))


def _first_index(rule: Rule, first: date) -> int:
    """A safe lower bound for the index of the first date on or after ``first``."""
    if first <= rule.start_date:
        return 0
    if rule.frequency == "monthly":
        months = (first.year - rule.start_date.year) * 12 + first.month - rule.start_date.month
        return max(0, months // rule.interval - 1)
    step = rule.interval * (7 if rule.frequency == "weekly" else 1)
    return max(0, (first - rule.start_date).days // step)


def occurrences(rule: Rule, first: date, last: date, limit: int = MAX_PER_PASS) -> list[date]:
    """Scheduled dates within [first, last], inclusive, honoring the until date."""
    if rule.until_date is not None:
        last = min(last, rule.until_date)
    result: list[date] = []
    n = _first_index(rule, first)
    while len(result) < limit:
        try:
            day = nth_date(rule, n)
        except (OverflowError, ValueError):
            break
        if day > last:
            break
        if day >= first:
            result.append(day)
        n += 1
    return result
