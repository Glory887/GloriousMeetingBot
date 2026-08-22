import logging
import sqlite3
from datetime import datetime, timedelta
from utils import format_datetime_moscow, format_datetime_utc
from db import get_user_lang, get_meeting_info
from config import DB_NAME

logger = logging.getLogger(__name__)

# Константы для напоминаний
REMIND_BEFORE_HOURS1 = 48
REMIND_BEFORE_HOURS2 = 24
REMIND_BEFORE_HOURS3 = 2
REMIND_BEFORE_HOURS4 = 1

def get_remind_datetime(date_str, time_str):
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

def restore_reminders(app):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, chat_id, user_id, date, time
        FROM meetings
        WHERE datetime(date || ' ' || time) > datetime('now')
    """)
    rows = cur.fetchall()
    conn.close()

    job_queue = app.job_queue
    if not job_queue:
        logger.warning("Job queue not available, reminders won't be restored.")
        return

    periods = {1: "2 дня", 2: "1 день", 3: "2 часа", 4: "1 час"}

    for meeting_id, chat_id, user_id, date_str, time_str in rows:
        remind_dt1, remind_dt2, remind_dt3, remind_dt4 = get_remind_datetime(date_str, time_str)
        remind_times = [remind_dt1, remind_dt2, remind_dt3, remind_dt4]
        if remind_dt4 < datetime.now():
            continue
        for i, remind_dt in enumerate(remind_times, start=1):
            existing_jobs = job_queue.get_jobs_by_name(f"reminder{i}_{meeting_id}")
            if existing_jobs:
                continue
            job_queue.run_once(
                callback=send_meeting_reminder,
                when=remind_dt,
                chat_id=chat_id,
                user_id=user_id,
                name=f"reminder{i}_{meeting_id}",
                data={"meeting_id": meeting_id, "period": periods[i]}
            )