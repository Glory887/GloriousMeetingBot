import zoneinfo
from datetime import datetime

# --- Month names dictionaries ---
MONTHS_RUS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

MONTHS_ENG = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


def format_datetime_moscow(date_str: str, time_str: str) -> str:
    """
    Convert UTC datetime to Moscow time (MSK) and format with Russian month names.
    Used for Russian language users.
    """
    moscow_tz = zoneinfo.ZoneInfo("Europe/Moscow")
    utc_tz = zoneinfo.ZoneInfo("UTC")
    dt_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt_utc = dt_utc.replace(tzinfo=utc_tz)
    dt_moscow = dt_utc.astimezone(moscow_tz)
    day = dt_moscow.day
    month = MONTHS_RUS[dt_moscow.month]
    year = dt_moscow.year
    hour = dt_moscow.hour
    minute = dt_moscow.minute
    return f"{day} {month} {year} {hour:02d}:{minute:02d}"


def format_datetime_utc(date_str: str, time_str: str) -> str:
    """
    Format UTC datetime with English month names.
    Used for English language users.
    """
    utc_tz = zoneinfo.ZoneInfo("UTC")
    dt_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt_utc = dt_utc.replace(tzinfo=utc_tz)
    day = dt_utc.day
    month = MONTHS_ENG[dt_utc.month]
    year = dt_utc.year
    hour = dt_utc.hour
    minute = dt_utc.minute
    return f"{day} {month} {year} {hour:02d}:{minute:02d} UTC"