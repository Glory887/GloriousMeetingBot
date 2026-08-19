import logging
import sqlite3
import locale
import requests
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ConversationHandler,
    filters,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
)
from datetime import datetime, timedelta
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
DB_NAME = "meetings.db"  # ваш реальный ключ
main_admin = 1644253455
REMIND_BEFORE_HOURS4 = 1
REMIND_BEFORE_HOURS3 = 2
REMIND_BEFORE_HOURS2 = 24
REMIND_BEFORE_HOURS1 = 48

# Состояния диалога (числа)
MENU, DATE, TIME, PLACE, COMMENT, LIST, INVITEE, ADMIN, ADMINLIST, DELETE, CITY = 887, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
exit = InlineKeyboardButton("Меню", callback_data="menu")

# ---------------------- Функция погоды ----------------------
async def get_weather_for_meeting(city: str, date_str: str, time_str: str) -> str:
    """
    Возвращает прогноз погоды в городе на указанную дату и время.
    date_str: "YYYY-MM-DD", time_str: "HH:MM"
    """
    url = (
        f"http://api.openweathermap.org/data/2.5/forecast"
        f"?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    )
    try:
        response = requests.get(url)
        data = response.json()
        if data.get("cod") != "200":
            return f"❌ Ошибка: {data.get('message', 'город не найден')}"

        meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        meeting_ts = int(meeting_dt.timestamp())

        best = None
        best_diff = float('inf')
        for forecast in data["list"]:
            diff = abs(forecast["dt"] - meeting_ts)
            if diff < best_diff:
                best_diff = diff
                best = forecast

        if best is None:
            return "❌ Прогноз на это время не найден."

        temp = best["main"]["temp"]
        feels_like = best["main"]["feels_like"]
        description = best["weather"][0]["description"]
        humidity = best["main"]["humidity"]
        wind = best["wind"]["speed"]

        forecast_time = datetime.fromtimestamp(best["dt"]).strftime("%d.%m.%Y %H:%M")
        return (
            f"🌤️ Прогноз погоды в {city} на {forecast_time}:\n"
            f"🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)\n"
            f"☁️ {description.capitalize()}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind} м/с\n"
        )
    except Exception as e:
        return f"⚠️ Ошибка при получении прогноза: {e}"

# ---------------------- Функции БД ----------------------
def format_date(date_str):
    """Преобразует 'YYYY-MM-DD' в 'DD Месяц YYYY' на русском."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day = dt.day
    month = MONTHS[dt.month]
    year = dt.year
    return f"{day} {month} {year}"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS meetings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        place TEXT NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        inviter_id INTEGER NOT NULL,
        invitee_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_admin INTEGER DEFAULT 0
    )""")
    cur.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cur.fetchall()]
    if 'is_admin' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if 'city' not in columns:   # отдельная проверка для city
        cur.execute("ALTER TABLE users ADD COLUMN city TEXT DEFAULT ''")
    conn.commit()
    conn.close()

def save_meeting(chat_id, user_id, date, time, place, comment):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO meetings (chat_id, user_id, date, time, place, comment)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (chat_id, user_id, date, time, place, comment))
    conn.commit()
    meeting_id = cur.lastrowid
    conn.close()
    return meeting_id

def get_all_meetings(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT meeting_id FROM invites WHERE invitee_id=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_meeting_info(meeting_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id,date,time,place,comment,created_at FROM meetings WHERE id=? ORDER BY created_at DESC",
        (meeting_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def AddInvite(meeting_id, inviter_id, invitee_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO invites(meeting_id, inviter_id, invitee_id) VALUES (?, ?, ?)",
        (meeting_id, inviter_id, invitee_id)
    )
    conn.commit()
    conn.close()

def get_status(meeting_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT status FROM invites WHERE meeting_id=? AND invitee_id=?", (meeting_id, user_id))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def update_status(meeting_id, user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE invites SET status=? WHERE meeting_id = ? AND invitee_id = ?",
        (status, meeting_id, user_id)
    )
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username, user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_all_status(meeting_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? and status='accepted'", (meeting_id,))
    accept = cur.fetchall()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? and status='pending'", (meeting_id,))
    pend = cur.fetchall()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? and status='declined'", (meeting_id,))
    decline = cur.fetchall()
    conn.close()
    return [accept, pend, decline]

def get_name_from_user_id(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None

def get_inviter_from_invitee(user_id, meeting_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT inviter_id FROM invites WHERE invitee_id = ? and meeting_id = ?",
        (user_id, meeting_id)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def delete_meeting(meeting_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()

def delete_invite(meeting_id, invitee_id):
    """Удаляет приглашение пользователя на встречу"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM invites WHERE meeting_id = ? AND invitee_id = ?",
        (meeting_id, invitee_id)
    )
    conn.commit()
    conn.close()

def change_mind(user_id, meeting_id, status):
    """Меняет статус пользователя на противоположный"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if status == "accepted":
        cur.execute(
            "UPDATE invites SET status=? WHERE meeting_id = ? AND invitee_id = ?",
            ("declined", meeting_id, user_id)
        )
    elif status == "declined":
        cur.execute(
            "UPDATE invites SET status=? WHERE meeting_id = ? AND invitee_id = ?",
            ("accepted", meeting_id, user_id)
        )
    conn.commit()
    conn.close()

def check_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,))
    answ = cur.fetchone()
    conn.close()
    if answ is None:
        return False
    return answ[0] == 1

def give_or_revoke_admin(user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()

def admin_list():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_admin=1")
    rows = cur.fetchall()
    conn.close()
    return rows

def user_exists(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def delete_user(user_id):
    """
    Удаляет пользователя из таблицы users,
    а также удаляет все его приглашения из invites.
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM invites WHERE invitee_id = ?", (user_id,))
    cur.execute("DELETE FROM invites WHERE inviter_id = ?", (user_id,))
    cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_remind_datetime(date_str, time_str):
    meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    remin_dt1 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS1)
    remin_dt2 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS2)
    remin_dt3 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS3)
    remin_dt4 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS4)
    return remin_dt1, remin_dt2, remin_dt3, remin_dt4

def restore_reminders(app):
    """Восстанавливает задачи напоминаний из БД при запуске"""
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

def get_city(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT city FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def update_city(user_id, city):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET city=? WHERE user_id=?", (city, user_id))
    conn.commit()   # исправлено: добавлены скобки
    conn.close()

# ---------------------- Обработчики ----------------------
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
            f"Встреча {format_date(row[1])}\n"
            f"Место: {row[3]}\n"
            f"Комментарий: {row[4] or 'отсутствует'}\n\n"
            f"До встречи осталось {hours}")
    await context.bot.send_message(chat_id=chat_id, text=text)

async def sendMENU(update_or_query, context):
    meeting_btn = InlineKeyboardButton("Назначить встречу", callback_data="meetings")
    list_btn = InlineKeyboardButton("Посмотреть список встреч", callback_data="lists")
    end_btn = InlineKeyboardButton("Завершить", callback_data="end")
    city_btn = InlineKeyboardButton("Изменить город", callback_data="city")

    if update_or_query.callback_query and update_or_query.callback_query.message:
        user_id = update_or_query.callback_query.from_user.id
    else:
        user_id = update_or_query.effective_user.id

    if user_id == main_admin:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn],
            [InlineKeyboardButton("Список пользователей", callback_data="user")],
            [InlineKeyboardButton("Список администраторов", callback_data="adminlist")]
        ]
    elif check_admin(user_id):
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn],
            [InlineKeyboardButton("Список пользователей", callback_data="user")]
        ]
    else:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn]
        ]

    if update_or_query.callback_query and update_or_query.callback_query.message:
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        chat_id = update_or_query.effective_chat.id

    await context.bot.send_message(
        chat_id=chat_id,
        text="Выберите опцию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
        (user_id, first_name, username)
    )
    conn.commit()
    conn.close()
    await sendMENU(update, context)
    return MENU

async def buttonreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "meetings":
        await query.edit_message_text(
            'Напиши, какого числа произойдет встреча (формат ДД.ММ.ГГГГ):\n\n'
            'Если передумаешь, пропиши /cancel'
        )
        return DATE

    elif data == "lists":
        user_id = query.from_user.id  # исправлено
        rows = get_all_meetings(user_id)
        meetings_count = 0

        for meeting_id in rows:
            meetings = get_meeting_info(meeting_id[0])
            if not meetings:
                delete_invite(meeting_id[0], user_id)
                continue

            for row in meetings:
                invite_btn = InlineKeyboardButton(
                    "Пригласить друга",
                    callback_data=f"invite_{row[0]}"
                )
                keyboard = [[invite_btn]]

                text = ""
                text += f"Дата: {format_date(row[1])}\n"
                text += f"Время: {row[2]}\n"
                text += f"Место: {row[3]}\n"
                text += f"Комментарий: {row[4]}\n\n"
                try:
                    meeting_datetime = datetime.strptime(f"{row[1]} {row[2]}", "%Y-%m-%d %H:%M")
                except ValueError:
                    # Если дата или время невалидны — удаляем встречу и пропускаем
                    delete_meeting(row[0])  # row[0] — ID встречи
                    continue

                if meeting_datetime < datetime.now():
                    delete_meeting(row[0])   # удаляем прошедшую встречу
                    continue
                city = get_city(user_id)
                if city:
                    weather_text = await get_weather_for_meeting(city, row[1], row[2])  # добавлен await
                    text += weather_text + "\n\n"
                else:
                    text += "ℹ️ Для прогноза погоды укажите город в меню.\n\n"

                answers = get_all_status(row[0])
                count = 0
                for i in answers[0]:
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} согласен✅\n"
                    count += 1
                for i in answers[1]:
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} не ответил🤨\n"
                for i in answers[2]:
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} отказался❌\n"

                if count == 0:
                    delete_meeting(row[0])
                    continue

                if count == 1 and get_status(row[0], user_id) == "accepted" or check_admin(user_id):
                    callback = f"delete_{row[0]}"
                    keyboard.append([InlineKeyboardButton("Отменить встречу", callback_data=callback)])

                callback = f"change_{row[0]}_{user_id}_{get_status(row[0], user_id)}"
                keyboard.append([InlineKeyboardButton("Изменить свой статус", callback_data=callback)])
                meetings_count += 1

                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        if not meetings_count:
            text = "Встречи не найдены!"
            await context.bot.send_message(chat_id=query.message.chat_id, text=text)

        await sendMENU(update, context)
        return MENU

    elif data.startswith("delete_"):
        meeting_id = int(data.split("_")[1])
        delete_meeting(meeting_id)
        text = "Встреча удалена."
        keyboard = [[exit]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MENU

    elif data.startswith("change_"):
        parts = data.split("_")
        meeting_id = int(parts[1])
        user_id = int(parts[2])
        status = parts[3]
        change_mind(user_id, meeting_id, status)
        rows = get_all_status(meeting_id)
        users = get_name_from_user_id(user_id)
        fname, uname = users
        keyboard = [[exit]]
        label = f"{fname} ({uname})" if fname and uname else fname or uname or str(user_id)

        if status == "accepted":
            for usid in rows[0]:
                text = "Вы отказались от встречи."
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await context.bot.send_message(
                    chat_id=usid[0],
                    text=f"Пользователь {label} отказался от приглашения("
                )
        else:
            for usid in rows[0]:
                text = "Вы согласились на встречу!"
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await context.bot.send_message(
                    chat_id=usid[0],
                    text=f"Пользователь {label} согласился на встречу!"
                )

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Статус изменён.",
            reply_markup=InlineKeyboardMarkup([[exit]])
        )
        return MENU

    elif data.startswith("invite_"):
        meeting_id = int(data.split("_")[1])
        users = get_all_users()
        keyboard = [[exit]]
        if not users:
            await query.edit_message_text(
                "Попроси друзей написать /start боту!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return MENU

        keyboard = []
        for fname, uname, uid in users:
            label = f"{fname} ({uname})" if fname and uname else fname or uname or str(uid)
            callback = f"pick_{meeting_id}_{uid}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback)])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="menu")])

        await query.edit_message_text(
            "Выберите пользователя для приглашения:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return INVITEE

    elif data.startswith("accept_") or data.startswith("decline_"):
        parts = data.split("_")
        user_id = int(parts[2])
        meeting_id = int(parts[1])
        uname, fname = get_name_from_user_id(user_id)
        name = f"{fname} ({uname})" if fname else uname
        inviter_id = get_inviter_from_invitee(user_id, meeting_id)

        if data.startswith("accept_"):
            status = "accepted"
            await query.edit_message_text("Ты принял приглашение!")
            if inviter_id:
                await context.bot.send_message(chat_id=inviter_id, text=f"Пользователь {name} принял приглашение!")
        else:
            status = "declined"
            await query.edit_message_text("Ты отказался от приглашения.")
            if inviter_id:
                await context.bot.send_message(chat_id=inviter_id, text=f"Пользователь {name} отказался от приглашения(")

        if inviter_id:
            update_status(meeting_id, user_id, status)
        else:
            await query.edit_message_text("Ошибка: приглашающий не найден. Статус не обновлён.")

        await sendMENU(update, context)
        return MENU

    elif data == "user":
        text = "Список всех пользователей:\n\n"
        user = get_all_users()
        i = 0
        for u in user:
            i += 1
            fname, uname, uid = u
            text += f"{i}. {fname} {uname} {uid}\n"
        keyboard = [[exit], [InlineKeyboardButton("Удалить пользователя", callback_data="deleteuser")]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MENU

    elif data == "deleteuser":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Введите ID пользователя")
        return DELETE

    elif data == "city":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Введите название города (на английском, например Moscow):")
        return CITY

    elif data == "admin":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Введите ID пользователя")
        return ADMIN

    elif data == "adminlist":
        return ADMINLIST

    elif data == "menu":
        await sendMENU(update, context)
        return MENU

    elif data == "end":
        await query.edit_message_text("До встречи!")
        return ConversationHandler.END

    return MENU

async def datereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text
    try:
        dt_obj = datetime.strptime(raw, "%d.%m.%Y")
        context.user_data['date'] = dt_obj.strftime("%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Неверный формат, используй ДД.ММ.ГГГГ")
        return DATE
    await update.message.reply_text('Отлично, во сколько хочешь встретиться? (формат ЧЧ:ММ)')
    return TIME

async def timereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text.strip()

    # 1. Проверяем формат и корректность времени
    try:
        datetime.strptime(time_str, "%H:%M")  # Если ошибка – значит невалидное время
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ, например 14:30"
        )
        return TIME  # остаёмся в состоянии TIME

    # 2. Сохраняем время в context
    context.user_data['time'] = time_str

    # 3. Проверяем, что дата+время не в прошлом
    date_str = context.user_data.get("date")
    if not date_str:
        await update.message.reply_text("Ошибка: дата не указана. Начните заново /start")
        return ConversationHandler.END

    try:
        meeting_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if meeting_datetime < datetime.now():
            await update.message.reply_text("❌ Эта дата и время уже прошли. Выберите будущее время.")
            return DATE  # возвращаем на ввод даты
    except ValueError:
        await update.message.reply_text("Ошибка в дате или времени. Попробуйте ещё раз.")
        return DATE

    # 4. Показываем погоду, если есть город
    keyboard = [[exit]]
    city = get_city(update.message.from_user.id)
    if city:
        weather = await get_weather_for_meeting(city, date_str, time_str)
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=weather,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="Если хотите увидеть прогноз погоды для своего города на этот день – введите название города в главном меню."
        )

    # 5. Переходим к месту
    await update.message.reply_text(
        'Какое прекрасное место станет вашей точкой встречи (лучше пиши с предлогом, например "в торговом центре")?'
    )
    return PLACE
async def placereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['place'] = update.message.text
    await update.message.reply_text('Желаешь ли ты оставить какой-либо комментарий?')
    return COMMENT

async def commentreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    date = context.user_data.get("date")
    time = context.user_data.get("time")
    place = context.user_data.get("place")
    comment = update.message.text

    meeting_id = save_meeting(chat_id, user_id, date, time, place, comment)
    AddInvite(meeting_id, user_id, user_id)
    update_status(meeting_id, user_id, "accepted")

    invite_btn = InlineKeyboardButton(
        "Пригласить друга",
        callback_data=f"invite_{meeting_id}"
    )
    keyboard = [[invite_btn], [exit]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'Окей, все запомнил и записал, скину напоминалки тебе и твоим друзьям',
        reply_markup=reply_markup
    )

    remind_dt1, remind_dt2, remind_dt3, remind_dt4 = get_remind_datetime(date, time)
    job_queue = context.application.job_queue

    if remind_dt4 > datetime.now():
        job_queue.run_once(
            callback=send_meeting_reminder,
            when=remind_dt4,
            chat_id=chat_id,
            user_id=user_id,
            name=f"reminder4_{meeting_id}",
            data={"period": "1 час", "meeting_id": meeting_id}
        )
        if remind_dt3 > datetime.now():
            job_queue.run_once(
                callback=send_meeting_reminder,
                when=remind_dt3,
                chat_id=chat_id,
                user_id=user_id,
                name=f"reminder3_{meeting_id}",
                data={"period": "2 часа", "meeting_id": meeting_id}
            )
            if remind_dt2 > datetime.now():
                job_queue.run_once(
                    callback=send_meeting_reminder,
                    when=remind_dt2,
                    chat_id=chat_id,
                    user_id=user_id,
                    name=f"reminder2_{meeting_id}",
                    data={"period": "1 день", "meeting_id": meeting_id}
                )
                if remind_dt1 > datetime.now():
                    job_queue.run_once(
                        callback=send_meeting_reminder,
                        when=remind_dt1,
                        chat_id=chat_id,
                        user_id=user_id,
                        name=f"reminder1_{meeting_id}",
                        data={"period": "2 дня", "meeting_id": meeting_id}
                    )

    return MENU

async def invitee_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pick_"):
        parts = data.split("_")
        meeting_id = int(parts[1])
        invitee_id = int(parts[2])
        inviter_id = query.from_user.id

        existing = get_status(meeting_id, invitee_id)
        if existing is not None:
            await query.edit_message_text("Этот пользователь уже приглашён на эту встречу.")
            await sendMENU(update, context)
            return MENU

        AddInvite(meeting_id, inviter_id, invitee_id)

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT date, time, place FROM meetings WHERE id = ?", (meeting_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            await query.edit_message_text("Встреча не найдена.")
            return MENU

        date, time, place = row
        try:
            await context.bot.send_message(
                chat_id=invitee_id,
                text=f"Тебя пригласили на встречу 😍\n\n"
                     f"{format_date(date)} в {time},\n встреча намечается {place} 🤯\n"
                     f"Ты придешь? 🤨",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Да, конечно!", callback_data=f"accept_{meeting_id}_{invitee_id}"),
                     InlineKeyboardButton("❌ Не, я пасс", callback_data=f"decline_{meeting_id}_{invitee_id}")]
                ])
            )
            await query.edit_message_text("Приглашение отправлено!")
        except Exception as e:
            await query.edit_message_text(
                f"Не удалось отправить приглашение. Возможно, пользователь ещё не писал боту.\n"
                f"Попросите написать /start, затем попробуйте снова."
            )

        await sendMENU(update, context)
        return MENU

    elif data == "menu":
        await sendMENU(update, context)
        return MENU

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[exit]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Окей, отменил твою встречу', reply_markup=reply_markup)
    return ConversationHandler.END

async def adminreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введите корректный числовой ID.")
        return ADMINLIST

    if user_exists(user_id):
        keyboard = [[InlineKeyboardButton("Открыть список администраторов", callback_data="adminlist")], [exit]]
        keyboardm = [[exit]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if check_admin(user_id):
            give_or_revoke_admin(user_id, 0)
            await update.message.reply_text('Права администратора изъяты', reply_markup=reply_markup)
            reply_markup = InlineKeyboardMarkup(keyboardm)
            await context.bot.send_message(chat_id=user_id, text="Права администратора изъяты", reply_markup=reply_markup)
        else:
            give_or_revoke_admin(user_id, 1)
            await update.message.reply_text('Выданы права администратора', reply_markup=reply_markup)
            reply_markup = InlineKeyboardMarkup(keyboardm)
            await context.bot.send_message(chat_id=user_id, text="Выданы права администратора", reply_markup=reply_markup)
    else:
        keyboard = [[exit]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text="Пользователь не найден, проверьте ID!", reply_markup=reply_markup)

    return ADMINLIST

async def adminlistreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin = admin_list()
    text = "Список админов:\n\n"
    i = 0
    for adm in admin:
        fname, uname = get_name_from_user_id(adm[0])
        i += 1
        text += f"{i}. {fname} {uname} {adm[0]}\n\n"

    keyboard = [[InlineKeyboardButton("Дать/забрать права администратора", callback_data="admin")], [exit]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_markup)
    return MENU

async def deletereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введите корректный числовой ID.")
        return MENU

    reply_markup = InlineKeyboardMarkup([[exit], [InlineKeyboardButton("Список пользователей", callback_data="user")]])
    if user_exists(user_id):
        delete_user(user_id)
        await update.message.reply_text("Пользователь удален", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Пользователя не существует. Проверьте ID", reply_markup=reply_markup)

    return MENU

async def cityreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    if not city:
        await update.message.reply_text("Введите корректное название города", reply_markup=InlineKeyboardMarkup([[exit]]))
        return CITY

    update_city(update.message.from_user.id, city)
    await update.message.reply_text(f"Город изменен на {city}", reply_markup=InlineKeyboardMarkup([[exit]]))
    return MENU

# ---------------------- Главная функция ----------------------
def main():
    init_db()
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(buttonreceived)
        ],
        states={
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, cityreceived)],
            DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletereceived)],
            ADMINLIST: [CallbackQueryHandler(adminlistreceived)],
            ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, adminreceived)],
            INVITEE: [CallbackQueryHandler(invitee_received)],
            MENU: [CallbackQueryHandler(buttonreceived)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, datereceived)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, timereceived)],
            PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, placereceived)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, commentreceived)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False
    )

    app = Application.builder().token(TOKEN).build()
    app.add_handler(conv_handler)
    restore_reminders(app)
    print("Гойда, братья!")
    app.run_polling()

if __name__ == "__main__":
    main()