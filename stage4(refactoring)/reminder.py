from config import DB_NAME,REMIND_BEFORE_HOURS1, REMIND_BEFORE_HOURS2, REMIND_BEFORE_HOURS3, REMIND_BEFORE_HOURS4
from datetime import datetime, timedelta
import sqlite3
from utils import format_datetime_moscow
from db import get_meeting_info
def get_remind_datetime(date_str, time_str):
    meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    remin_dt1 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS1)
    remin_dt2 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS2)
    remin_dt3 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS3)
    remin_dt4 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS4)
    return remin_dt1, remin_dt2, remin_dt3, remin_dt4

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
async def send_meeting_reminder(context):
    job = context.job
    hours = job.data.get("period", "1 час")
    meeting_id = job.data.get("meeting_id")
    chat_id = job.chat_id
    meeting_info = get_meeting_info(meeting_id)
    if not meeting_info:
        return
    row = meeting_info[0]
    text = (f"Напоминание о встрече!\n\n"
            f"Встреча {format_datetime_moscow(row[1],row[2])}(По МСК)\n"
            f"Место: {row[3]}\n"
            f"Комментарий: {row[4] or 'отсутствует'}\n\n"
            f"До встречи осталось {hours}")
    await context.bot.send_message(chat_id=chat_id, text=text)