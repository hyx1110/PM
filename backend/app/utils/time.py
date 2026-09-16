from datetime import date, datetime
from zoneinfo import ZoneInfo

BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    """Return a timezone-naive Beijing datetime for MySQL DATETIME columns."""
    return datetime.now(BEIJING_TIMEZONE).replace(tzinfo=None)


def beijing_today() -> date:
    return beijing_now().date()
