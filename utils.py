import zoneinfo
from datetime import datetime

MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

def format_datetime_moscow(date_str: str, time_str: str) -> str:
    """Преобразует UTC дату и время в строку с московским временем и русским месяцем."""
    moscow_tz = zoneinfo.ZoneInfo("Europe/Moscow")
    utc_tz = zoneinfo.ZoneInfo("UTC")
    dt_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt_utc = dt_utc.replace(tzinfo=utc_tz)
    dt_moscow = dt_utc.astimezone(moscow_tz)
    day = dt_moscow.day
    month = MONTHS[dt_moscow.month]
    year = dt_moscow.year
    hour = dt_moscow.hour
    minute = dt_moscow.minute
    return f"{day} {month} {year} {hour:02d}:{minute:02d}"

def format_datetime_utc(date_str: str, time_str: str) -> str:
    """Преобразует UTC дату и время в строку с UTC временем (без перевода в МСК)."""
    dt_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    # Оставляем как UTC, выводим в формате ГГГГ-ММ-ДД ЧЧ:ММ UTC
    return dt_utc.strftime("%Y-%m-%d %H:%M UTC")