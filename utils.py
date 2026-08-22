import zoneinfo
from datetime import datetime
from config import MONTHS
def format_datetime_moscow(date_str: str, time_str: str) -> str:
    """Преобразует UTC дату и время в строку с московским временем и русским месяцем."""
    moscow_tz = zoneinfo.ZoneInfo("Europe/Moscow")
    utc_tz = zoneinfo.ZoneInfo("UTC")
    # Парсим как UTC
    dt_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt_utc = dt_utc.replace(tzinfo=utc_tz)
    # Переводим в Москву
    dt_moscow = dt_utc.astimezone(moscow_tz)
    # Форматируем с русским месяцем
    day = dt_moscow.day
    month = MONTHS[dt_moscow.month]
    year = dt_moscow.year
    hour = dt_moscow.hour
    minute = dt_moscow.minute
    return f"{day} {month} {year} {hour:02d}:{minute:02d}"