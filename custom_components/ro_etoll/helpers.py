"""Pure helpers for the portal's verification data and Romanian timestamps."""

from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from .const import PURCHASED_STATUSES, SERVICE_STATUSES

ROMANIA_TZ = ZoneInfo("Europe/Bucharest")


def parse_datetime(value: Any, *, end_of_day: bool = False) -> datetime | None:
    """Parse API ISO dates (and numeric seconds/milliseconds) as aware UTC."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(
                value / 1000 if abs(value) >= 10**11 else value, timezone.utc
            )
        if not isinstance(value, str) or not value.strip():
            return None
        value = value.strip()
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if len(value) == 10 and end_of_day:
            dt = datetime.combine(dt.date(), time.max)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ROMANIA_TZ)
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def section_items(verification: Any, section: str) -> list[dict] | None:
    """Missing/unavailable sections are unknown, not empty results."""
    if not isinstance(verification, dict):
        return None
    data = verification.get(section)
    if not isinstance(data, dict) or data.get("status") != "OK":
        return None
    items = data.get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        return None
    return items


def section_status(verification: Any, section: str) -> str:
    """Return a bounded diagnostic code, never arbitrary response content."""
    if not isinstance(verification, dict):
        return "REQUEST_FAILED"
    if section not in verification:
        return "MISSING_SECTION"
    data = verification[section]
    if data is None:
        return "REQUEST_FAILED"
    if not isinstance(data, dict):
        return "INVALID_RESPONSE"
    if data.get("status") == "UNAVAILABLE":
        return "UNAVAILABLE"
    if data.get("status") != "OK":
        return "UNKNOWN_STATUS"
    return (
        "OK" if section_items(verification, section) is not None else "INVALID_RESPONSE"
    )


def item_active(item: dict, now: datetime) -> bool | None:
    start_raw, end_raw = item.get("validityStartDate"), item.get("validityEndDate")
    start = parse_datetime(start_raw)
    end = parse_datetime(end_raw, end_of_day=True)
    if (start_raw is not None and start is None) or (
        end_raw is not None and end is None
    ):
        return None
    if start is not None and now < start:
        return False
    if end is not None and now > end:
        return False
    if isinstance(item.get("active"), bool):
        return item["active"]
    if start is not None and end is not None:
        return True
    return None


def vignette_active(items: list[dict] | None, now: datetime) -> bool | None:
    if items is None:
        return None
    values = [item_active(item, now) for item in items]
    if True in values:
        return True
    return None if None in values else False


def select_vignette(items: list[dict], now: datetime) -> dict | None:
    """Prefer an active vignette, then the next scheduled one, then history."""

    def end(item: dict) -> float:
        value = parse_datetime(item.get("validityEndDate"), end_of_day=True)
        return value.timestamp() if value else 0

    active = [item for item in items if item_active(item, now) is True]
    if active:
        return max(active, key=end)
    future = [
        (start, item)
        for item in items
        if (start := parse_datetime(item.get("validityStartDate"))) is not None
        and start > now
    ]
    if future:
        return min(future, key=lambda pair: pair[0])[1]
    return max(items, key=end) if items else None


def numeric(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def bridge_balance(items: list[dict] | None, now: datetime) -> float | None:
    """Count usable crossings only when the required balance/validity is known."""
    if items is None:
        return None
    total = Decimal(0)
    for item in items:
        active = item_active(item, now)
        remaining = numeric(item.get("remainingBalance"))
        if active is False or remaining == 0:
            continue
        if active is None or remaining is None or remaining < 0:
            return None
        total += remaining
    return float(total)


def bridge_crossings(items: list[dict] | None) -> list[dict] | None:
    """Distinguish explicitly empty crossing lists from missing detail."""
    if items is None:
        return None
    result = []
    for item in items:
        crossings = item.get("crossings")
        if not isinstance(crossings, list) or any(
            not isinstance(crossing, dict) for crossing in crossings
        ):
            return None
        result.extend(crossings)
    return result


def sanitize_plate_no(plate_no: str) -> str:
    """Retain the original integration's unique-ID convention."""
    return plate_no.replace(" ", "_").lower()


def invoice_amount(invoice: dict) -> Decimal | None:
    total = invoice.get("total")
    return numeric(total.get("totalPrice") if isinstance(total, dict) else total)


def period_start(now: datetime, period: str) -> datetime:
    local = now.astimezone(ROMANIA_TZ)
    return local.replace(
        month=1 if period == "year" else local.month,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    ).astimezone(timezone.utc)


def invoice_period_total(
    invoices: list[dict] | None, now: datetime, period: str
) -> Decimal | None:
    """Sum payments in Romanian calendar periods; incomplete values stay unknown."""
    if invoices is None:
        return None
    start = period_start(now, period)
    total = Decimal(0)
    for invoice in invoices:
        paid = parse_datetime(invoice.get("paymentDate"))
        if paid is None:
            return None
        if start <= paid <= now:
            amount = invoice_amount(invoice)
            if amount is None:
                return None
            total += amount
    return total


def latest_record(items: list[dict] | None, key: str) -> dict | None:
    """An undated record prevents establishing which record is latest."""
    if not items:
        return None
    dates = [parse_datetime(item.get(key)) for item in items]
    if any(value is None for value in dates):
        return None
    return items[max(range(len(items)), key=lambda index: dates[index])]


def purchased_services(items: list[dict] | None) -> list[dict] | None:
    if items is None or any(
        not isinstance(item.get("status"), str)
        or item["status"] not in SERVICE_STATUSES
        for item in items
    ):
        return None
    return [item for item in items if item["status"] in PURCHASED_STATUSES]


def purchase_date(item: dict) -> datetime | None:
    """Match GetPurchaseDate in the portal client."""
    kind = item.get("type")
    if kind in ("VIGNETTE", 0):
        keys = ("vignetteIssueDate", "ticketCreatedAt")
    elif kind in ("BRIDGE", 1):
        keys = ("peajIssueDate", "ticketCreatedAt")
    elif kind in ("PER_KM", 3):
        keys = ("ticketCreatedAt", "firstTransactionDate")
    else:
        keys = ("ticketCreatedAt",)
    for key in keys:
        if item.get(key) is not None:
            return parse_datetime(item[key])
    return None


def next_vignette(items: list[dict] | None, now: datetime) -> dict | None:
    if items is None:
        return None
    future = [
        (start, item)
        for item in items
        if (start := parse_datetime(item.get("validityStartDate"))) is not None
        and start > now
        and (end := parse_datetime(item.get("validityEndDate"), end_of_day=True))
        is not None
        and end >= start
    ]
    return min(future, key=lambda pair: pair[0])[1] if future else None
