import logging
from datetime import datetime, timedelta
from utils import format_datetime_moscow, format_datetime_utc
from db import get_user_lang, get_meeting_info

logger = logging.getLogger(__name__)

# Константы для напоминаний (можно вынести в config)
REMIND_BEFORE_HOURS1 = 48
REMIND_BEFORE_HOURS2 = 24
REMIND_BEFORE_HOURS3 = 2
REMIND_BEFORE_HOURS4 = 1

def get_remind_datetime(date_str, time_str):
    """Возвращает четыре времени для напоминаний: за 48ч, 24ч, 2ч, 1ч до встречи."""
    meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    remind_dt1 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS1)
    remind_dt2 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS2)
    remind_dt3 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS3)
    remind_dt4 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS4)
    return remind_dt1, remind_dt2, remind_dt3, remind_dt4

async def send_meeting_reminder(context):
    job = context.job
    meeting_id = job.data.get("meeting_id")
    chat_id = job.chat_id
    user_id = job.user_id
    period = job.data.get("period", "1 час")

    lang = get_user_lang(user_id)
    meeting_info = get_meeting_info(meeting_id)
    if not meeting_info:
        logger.warning(f"Meeting {meeting_id} not found for reminder")
        return
    row = meeting_info[0]
    date_str = row[1]
    time_str = row[2]
    place = row[3]
    comment = row[4] or ('отсутствует' if lang == 'ru' else 'none')

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