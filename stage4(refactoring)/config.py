import os
import logging
import zoneinfo
from telegram import InlineKeyboardButton
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")
TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY')
DB_NAME = "meetings.db"  
main_admin = 1644253455
REMIND_BEFORE_HOURS4 = 1
REMIND_BEFORE_HOURS3 = 2
REMIND_BEFORE_HOURS2 = 24
REMIND_BEFORE_HOURS1 = 48

menu_btn = InlineKeyboardButton("Меню", callback_data="menu")
MENU, DATE, TIME, PLACE, COMMENT, LIST, INVITEE, ADMIN, ADMINLIST, DELETE, CITY, = 887, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10