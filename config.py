import os
import logging
import zoneinfo
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")
MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY')
DB_NAME = "meetings.db"  # ваш реальный ключ
main_admin = 1644253455
REMIND_BEFORE_HOURS4 = 1
REMIND_BEFORE_HOURS3 = 2
REMIND_BEFORE_HOURS2 = 24
REMIND_BEFORE_HOURS1 = 48

# Состояния диалога (числа)
MENU, DATE, TIME, PLACE, COMMENT, LIST, INVITEE, ADMIN, ADMINLIST, DELETE, CITY, = 887, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10