from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from dateutil import parser as date_parser


def parse_datetime(date_input: any) -> Optional[datetime]:
    """Parse various RSS/HTTP/string date formats into a timezone-aware UTC datetime."""
    if not date_input:
        return None

    # Handle struct_time or time tuple from feedparser
    if hasattr(date_input, "tm_year"):
        try:
            return datetime(
                year=date_input.tm_year,
                month=date_input.tm_mon,
                day=date_input.tm_mday,
                hour=date_input.tm_hour,
                minute=date_input.tm_min,
                second=date_input.tm_sec,
                tzinfo=timezone.utc,
            )
        except Exception:
            pass

    if isinstance(date_input, datetime):
        if date_input.tzinfo is None:
            return date_input.replace(tzinfo=timezone.utc)
        return date_input.astimezone(timezone.utc)

    if isinstance(date_input, str):
        try:
            dt = date_parser.parse(date_input)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return None

    return None


def is_within_last_24_hours(
    pub_dt: datetime,
    max_hours: float = 24.0,
    reference_time: Optional[datetime] = None,
) -> Tuple[bool, float]:
    """Check if the given datetime is within the last `max_hours` (default 24h).

    Returns:
        (is_within_24h: bool, age_in_hours: float)
    """
    if pub_dt is None:
        return False, 999.0

    ref = reference_time or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    diff = ref - pub_dt
    age_hours = diff.total_seconds() / 3600.0

    # Article must be published within the last 24h, and not far into future
    is_valid = -1.0 <= age_hours <= max_hours
    return is_valid, max(0.0, age_hours)


def get_today_date_str() -> str:
    """Return today's date formatted as YYYY-MM-DD in UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
