import logging
from datetime import datetime
from utils import format_datetime_moscow, format_datetime_utc
from db import get_user_lang, get_meeting_info

logger = logging.getLogger(__name__)

async def send_meeting_reminder(context):
    job = context.job
    meeting_id = job.data.get("meeting_id")
    chat_id = job.chat_id
    user_id = job.user_id  # пользователь, которому отправляем напоминание (создатель встречи)
    period = job.data.get("period", "1 час")

    # Получаем язык пользователя из БД
    lang = get_user_lang(user_id)  # 'ru' или 'en'

    # Получаем данные встречи
    meeting_info = get_meeting_info(meeting_id)
    if not meeting_info:
        logger.warning(f"Meeting {meeting_id} not found for reminder")
        return
    row = meeting_info[0]  # (id, date, time, place, comment, created_at)
    date_str = row[1]
    time_str = row[2]
    place = row[3]
    comment = row[4] or 'отсутствует' if lang == 'ru' else 'none'

    # Форматируем дату в зависимости от языка
    if lang == 'en':
        date_formatted = format_datetime_utc(date_str, time_str)
        text = (f"Meeting reminder!\n\n"
                f"Meeting at {date_formatted} (UTC)\n"
                f"Place: {place}\n"
                f"Comment: {comment}\n\n"
                f"Time until meeting: {period}")
    else:
        date_formatted = format_datetime_moscow(date_str, time_str)
        text = (f"Напоминание о встрече!\n\n"
                f"Встреча {date_formatted} (МСК)\n"
                f"Место: {place}\n"
                f"Комментарий: {comment}\n\n"
                f"До встречи осталось {period}")

    await context.bot.send_message(chat_id=chat_id, text=text)