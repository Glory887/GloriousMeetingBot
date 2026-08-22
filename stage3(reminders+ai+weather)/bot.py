# -*- coding: utf-8 -*-

# --- IMPORTS ---
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

# --- LOGGING SETUP ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- LOCALE FOR RUSSIAN MONTH NAMES ---
try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except:
    locale.setlocale(locale.LC_TIME, 'Russian_Russia')

# --- ENVIRONMENT VARIABLES ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
DB_NAME = "meetings.db"

# --- CONSTANTS ---
main_admin = 1644253455   # hardcoded main admin ID

# Reminder intervals (hours before meeting)
REMIND_BEFORE_HOURS4 = 1
REMIND_BEFORE_HOURS3 = 2
REMIND_BEFORE_HOURS2 = 24
REMIND_BEFORE_HOURS1 = 48

# Conversation states
MENU, DATE, TIME, PLACE, COMMENT, LIST, INVITEE, ADMIN, ADMINLIST, DELETE, CITY = 887, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10

# Global "Menu" button for reuse
exit_btn = InlineKeyboardButton("Menu", callback_data="menu")


# --- WEATHER FUNCTION (NEW) ---
async def get_weather_for_meeting(city: str, date_str: str, time_str: str) -> str:
    """
    Fetches weather forecast for a given city and meeting time.
    Parameters:
        city – city name (in English)
        date_str – date in "YYYY-MM-DD" format
        time_str – time in "HH:MM" format
    Returns formatted weather string or error message.
    """
    url = (
        f"http://api.openweathermap.org/data/2.5/forecast"
        f"?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    )
    try:
        response = requests.get(url)
        data = response.json()
        if data.get("cod") != "200":
            return f"❌ Error: {data.get('message', 'city not found')}"

        meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        meeting_ts = int(meeting_dt.timestamp())

        # Find forecast closest to meeting time
        best = None
        best_diff = float('inf')
        for forecast in data["list"]:
            diff = abs(forecast["dt"] - meeting_ts)
            if diff < best_diff:
                best_diff = diff
                best = forecast

        if best is None:
            return "❌ Forecast not found for this time."

        temp = best["main"]["temp"]
        feels_like = best["main"]["feels_like"]
        description = best["weather"][0]["description"]
        humidity = best["main"]["humidity"]
        wind = best["wind"]["speed"]

        forecast_time = datetime.fromtimestamp(best["dt"]).strftime("%d.%m.%Y %H:%M")
        return (
            f"🌤️ Weather forecast in {city} for {forecast_time}:\n"
            f"🌡️ Temperature: {temp}°C (feels like {feels_like}°C)\n"
            f"☁️ {description.capitalize()}\n"
            f"💧 Humidity: {humidity}%\n"
            f"💨 Wind: {wind} m/s\n"
        )
    except Exception as e:
        return f"⚠️ Error retrieving forecast: {e}"


# --- HELPER: Format date (NEW) ---
def format_date(date_str):
    """Convert 'YYYY-MM-DD' to 'DD Month YYYY' in Russian (locale-dependent)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%d %B %Y")


# --- DATABASE FUNCTIONS (extended) ---
def init_db():
    """Create tables if not exist, add 'city' column to users if missing."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Meetings table
    cur.execute("""CREATE TABLE IF NOT EXISTS meetings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        place TEXT NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # Invites table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        inviter_id INTEGER NOT NULL,
        invitee_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    )""")

    # Users table (with is_admin, city)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_admin INTEGER DEFAULT 0
    )""")

    # Migrations: add is_admin and city if missing
    cur.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cur.fetchall()]
    if 'is_admin' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if 'city' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN city TEXT DEFAULT ''")

    conn.commit()
    conn.close()


def save_meeting(chat_id, user_id, date, time, place, comment):
    """Insert meeting and return its ID."""
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
    """Return list of meeting IDs where the user is invited."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT meeting_id FROM invites WHERE invitee_id=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_meeting_info(meeting_id):
    """Return full meeting details by ID."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, date, time, place, comment, created_at FROM meetings WHERE id=? ORDER BY created_at DESC",
        (meeting_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def AddInvite(meeting_id, inviter_id, invitee_id):
    """Insert invitation with 'pending' status."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO invites(meeting_id, inviter_id, invitee_id) VALUES (?, ?, ?)",
        (meeting_id, inviter_id, invitee_id)
    )
    conn.commit()
    conn.close()


def get_status(meeting_id, user_id):
    """Return invitation status (or None)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT status FROM invites WHERE meeting_id=? AND invitee_id=?", (meeting_id, user_id))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def update_status(meeting_id, user_id, status):
    """Update invitation status."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE invites SET status=? WHERE meeting_id = ? AND invitee_id = ?",
        (status, meeting_id, user_id)
    )
    conn.commit()
    conn.close()


def get_all_users():
    """Return all users: (first_name, username, user_id)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username, user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_status(meeting_id):
    """Return three lists: accepted, pending, declined invitees."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? AND status='accepted'", (meeting_id,))
    accept = cur.fetchall()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? AND status='pending'", (meeting_id,))
    pend = cur.fetchall()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? AND status='declined'", (meeting_id,))
    decline = cur.fetchall()
    conn.close()
    return [accept, pend, decline]


def get_name_from_user_id(user_id):
    """Return (first_name, username) for a user ID."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None


def get_inviter_from_invitee(user_id, meeting_id):
    """Return ID of user who invited the given user to this meeting."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT inviter_id FROM invites WHERE invitee_id = ? AND meeting_id = ?",
        (user_id, meeting_id)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def delete_meeting(meeting_id):
    """Delete meeting (invites cascade)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()


def delete_invite(meeting_id, invitee_id):
    """Delete a specific invitation."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM invites WHERE meeting_id = ? AND invitee_id = ?",
        (meeting_id, invitee_id)
    )
    conn.commit()
    conn.close()


def change_mind(user_id, meeting_id, status):
    """Toggle user's status between accepted/declined."""
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
    """Return True if user is admin."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,))
    answ = cur.fetchone()
    conn.close()
    if answ is None:
        return False
    return answ[0] == 1


def give_or_revoke_admin(user_id, status):
    """Set admin status (1 or 0) for a user."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()


def admin_list():
    """Return list of admin user IDs."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_admin=1")
    rows = cur.fetchall()
    conn.close()
    return rows


def user_exists(user_id):
    """Check if a user exists in users table."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def delete_user(user_id):
    """Delete user and clean their invites (both as inviter and invitee)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM invites WHERE invitee_id = ?", (user_id,))
    cur.execute("DELETE FROM invites WHERE inviter_id = ?", (user_id,))
    cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_city(user_id):
    """Return user's city (or None)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT city FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def update_city(user_id, city):
    """Update user's city."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET city=? WHERE user_id=?", (city, user_id))
    conn.commit()
    conn.close()


# --- REMINDER SYSTEM (NEW) ---
def get_remind_datetime(date_str, time_str):
    """
    Calculate four reminder times: 48h, 24h, 2h, 1h before meeting.
    """
    meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    remind_dt1 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS1)
    remind_dt2 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS2)
    remind_dt3 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS3)
    remind_dt4 = meeting_dt - timedelta(hours=REMIND_BEFORE_HOURS4)
    return remind_dt1, remind_dt2, remind_dt3, remind_dt4


def restore_reminders(app):
    """Restore reminder jobs from database on bot startup."""
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

    periods = {1: "2 days", 2: "1 day", 3: "2 hours", 4: "1 hour"}

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
    """Send reminder message to the user."""
    job = context.job
    hours = job.data.get("period", "1 hour")
    meeting_id = job.data.get("meeting_id")
    chat_id = job.chat_id
    meeting_info = get_meeting_info(meeting_id)
    if not meeting_info:
        return
    row = meeting_info[0]
    text = (f"Meeting reminder!\n\n"
            f"Meeting on {format_date(row[1])}\n"
            f"Place: {row[3]}\n"
            f"Comment: {row[4] or 'none'}\n\n"
            f"Time until meeting: {hours}")
    await context.bot.send_message(chat_id=chat_id, text=text)


# --- HANDLERS ---
async def sendMENU(update_or_query, context):
    """
    Send main menu with inline buttons.
    Shows admin-specific buttons if the user is admin/main_admin.
    """
    meeting_btn = InlineKeyboardButton("Schedule meeting", callback_data="meetings")
    list_btn = InlineKeyboardButton("View meetings", callback_data="lists")
    end_btn = InlineKeyboardButton("Finish", callback_data="end")
    city_btn = InlineKeyboardButton("Change city", callback_data="city")   # NEW

    # Determine user_id
    if update_or_query.callback_query and update_or_query.callback_query.message:
        user_id = update_or_query.callback_query.from_user.id
    else:
        user_id = update_or_query.effective_user.id

    # Keyboard based on user role
    if user_id == main_admin:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn],
            [InlineKeyboardButton("User list", callback_data="user")],
            [InlineKeyboardButton("Admin list", callback_data="adminlist")]
        ]
    elif check_admin(user_id):
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn],
            [InlineKeyboardButton("User list", callback_data="user")]
        ]
    else:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn]
        ]

    # Determine chat_id
    if update_or_query.callback_query and update_or_query.callback_query.message:
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        chat_id = update_or_query.effective_chat.id

    await context.bot.send_message(
        chat_id=chat_id,
        text="Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start — register user and show menu."""
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
    """Main callback handler for all inline buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "meetings":
        # Start meeting creation — ask for date
        await query.edit_message_text(
            'Enter meeting date (DD.MM.YYYY):\n\n'
            'If you change your mind, type /cancel'
        )
        return DATE

    elif data == "lists":
        # Show meeting list with weather and participant statuses
        user_id = query.from_user.id
        rows = get_all_meetings(user_id)
        meetings_count = 0

        for meeting_id in rows:
            meetings = get_meeting_info(meeting_id[0])
            if not meetings:
                delete_invite(meeting_id[0], user_id)
                continue

            for row in meetings:
                invite_btn = InlineKeyboardButton(
                    "Invite friend",
                    callback_data=f"invite_{row[0]}"
                )
                keyboard = [[invite_btn]]

                text = ""
                text += f"Date: {format_date(row[1])}\n"
                text += f"Time: {row[2]}\n"
                text += f"Place: {row[3]}\n"
                text += f"Comment: {row[4]}\n\n"
                try:
                    meeting_datetime = datetime.strptime(f"{row[1]} {row[2]}", "%Y-%m-%d %H:%M")
                except ValueError:
                    delete_meeting(row[0])
                    continue

                if meeting_datetime < datetime.now():
                    delete_meeting(row[0])
                    continue

                # Weather
                city = get_city(user_id)
                if city:
                    weather_text = await get_weather_for_meeting(city, row[1], row[2])
                    text += weather_text + "\n\n"
                else:
                    text += "ℹ️ To get weather forecast, set your city in the menu.\n\n"

                # Participant statuses
                answers = get_all_status(row[0])
                count = 0
                for i in answers[0]:
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} ✅\n"
                    count += 1
                for i in answers[1]:
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} 🤨\n"
                for i in answers[2]:
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} ❌\n"

                if count == 0:
                    delete_meeting(row[0])
                    continue

                # Cancel meeting button — if only one accepted (current user) or admin
                if count == 1 and get_status(row[0], user_id) == "accepted" or check_admin(user_id):
                    callback = f"delete_{row[0]}"
                    keyboard.append([InlineKeyboardButton("Cancel meeting", callback_data=callback)])

                # Change status button
                callback = f"change_{row[0]}_{user_id}_{get_status(row[0], user_id)}"
                keyboard.append([InlineKeyboardButton("Change my status", callback_data=callback)])
                meetings_count += 1

                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        if not meetings_count:
            text = "No meetings found!"
            await context.bot.send_message(chat_id=query.message.chat_id, text=text)

        await sendMENU(update, context)
        return MENU

    elif data.startswith("delete_"):
        meeting_id = int(data.split("_")[1])
        delete_meeting(meeting_id)
        text = "Meeting deleted."
        keyboard = [[exit_btn]]
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
        keyboard = [[exit_btn]]
        label = f"{fname} ({uname})" if fname and uname else fname or uname or str(user_id)

        if status == "accepted":
            for usid in rows[0]:
                text = "You declined the invitation."
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await context.bot.send_message(
                    chat_id=usid[0],
                    text=f"{label} declined the invitation("
                )
        else:
            for usid in rows[0]:
                text = "You accepted the invitation!"
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await context.bot.send_message(
                    chat_id=usid[0],
                    text=f"{label} accepted the invitation!"
                )

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Status changed.",
            reply_markup=InlineKeyboardMarkup([[exit_btn]])
        )
        return MENU

    elif data.startswith("invite_"):
        meeting_id = int(data.split("_")[1])
        users = get_all_users()
        keyboard = [[exit_btn]]
        if not users:
            await query.edit_message_text(
                "Ask your friends to start the bot!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return MENU

        keyboard = []
        for fname, uname, uid in users:
            label = f"{fname} ({uname})" if fname and uname else fname or uname or str(uid)
            callback = f"pick_{meeting_id}_{uid}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback)])
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="menu")])

        await query.edit_message_text(
            "Choose a user to invite:",
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
            await query.edit_message_text("You accepted the invitation!")
            if inviter_id:
                await context.bot.send_message(chat_id=inviter_id, text=f"{name} accepted the invitation!")
        else:
            status = "declined"
            await query.edit_message_text("You declined the invitation.")
            if inviter_id:
                await context.bot.send_message(chat_id=inviter_id, text=f"{name} declined the invitation(")

        if inviter_id:
            update_status(meeting_id, user_id, status)
        else:
            await query.edit_message_text("Error: inviter not found. Status not updated.")

        await sendMENU(update, context)
        return MENU

    elif data == "user":
        # Admin-only: list all users
        text = "List of all users:\n\n"
        users = get_all_users()
        i = 0
        for u in users:
            i += 1
            fname, uname, uid = u
            text += f"{i}. {fname} {uname} {uid}\n"
        keyboard = [[exit_btn], [InlineKeyboardButton("Delete user", callback_data="deleteuser")]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MENU

    elif data == "deleteuser":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Enter user ID:")
        return DELETE

    elif data == "city":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Enter your city name (in English, e.g. Moscow):")
        return CITY

    elif data == "admin":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Enter user ID:")
        return ADMIN

    elif data == "adminlist":
        return ADMINLIST

    elif data == "menu":
        await sendMENU(update, context)
        return MENU

    elif data == "end":
        await query.edit_message_text("See you later!")
        return ConversationHandler.END

    return MENU


# --- MEETING CREATION STEP HANDLERS ---
async def datereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive date, store, and ask for time."""
    raw = update.message.text
    try:
        dt_obj = datetime.strptime(raw, "%d.%m.%Y")
        context.user_data['date'] = dt_obj.strftime("%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Invalid format, use DD.MM.YYYY")
        return DATE
    await update.message.reply_text('Great! What time? (HH:MM format)')
    return TIME


async def timereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receive time, validate format and future time,
    show weather if city set, then ask for place.
    """
    time_str = update.message.text.strip()

    # Validate time format
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid time format. Enter time as HH:MM, e.g. 14:30"
        )
        return TIME

    context.user_data['time'] = time_str

    date_str = context.user_data.get("date")
    if not date_str:
        await update.message.reply_text("Error: date not set. Please restart /start")
        return ConversationHandler.END

    try:
        meeting_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if meeting_datetime < datetime.now():
            await update.message.reply_text("❌ This date and time have already passed. Choose a future time.")
            return DATE
    except ValueError:
        await update.message.reply_text("Error in date or time. Please try again.")
        return DATE

    # Show weather if city is set
    keyboard = [[exit_btn]]
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
            text="If you want to see weather forecast, set your city in the main menu."
        )

    await update.message.reply_text(
        'What wonderful place will be your meeting point? (e.g. "in the mall")'
    )
    return PLACE


async def placereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive place, ask for comment."""
    context.user_data['place'] = update.message.text
    await update.message.reply_text('Would you like to leave any comment?')
    return COMMENT


async def commentreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receive comment, save meeting, add creator as participant,
    schedule reminders, and return to menu.
    """
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
        "Invite friend",
        callback_data=f"invite_{meeting_id}"
    )
    keyboard = [[invite_btn], [exit_btn]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'Okay, I’ve saved everything. I\'ll send reminders to you and your friends.',
        reply_markup=reply_markup
    )

    # Schedule reminders
    remind_dt1, remind_dt2, remind_dt3, remind_dt4 = get_remind_datetime(date, time)
    job_queue = context.application.job_queue

    if remind_dt4 > datetime.now():
        job_queue.run_once(
            callback=send_meeting_reminder,
            when=remind_dt4,
            chat_id=chat_id,
            user_id=user_id,
            name=f"reminder4_{meeting_id}",
            data={"period": "1 hour", "meeting_id": meeting_id}
        )
        if remind_dt3 > datetime.now():
            job_queue.run_once(
                callback=send_meeting_reminder,
                when=remind_dt3,
                chat_id=chat_id,
                user_id=user_id,
                name=f"reminder3_{meeting_id}",
                data={"period": "2 hours", "meeting_id": meeting_id}
            )
            if remind_dt2 > datetime.now():
                job_queue.run_once(
                    callback=send_meeting_reminder,
                    when=remind_dt2,
                    chat_id=chat_id,
                    user_id=user_id,
                    name=f"reminder2_{meeting_id}",
                    data={"period": "1 day", "meeting_id": meeting_id}
                )
                if remind_dt1 > datetime.now():
                    job_queue.run_once(
                        callback=send_meeting_reminder,
                        when=remind_dt1,
                        chat_id=chat_id,
                        user_id=user_id,
                        name=f"reminder1_{meeting_id}",
                        data={"period": "2 days", "meeting_id": meeting_id}
                    )

    return MENU


# --- INVITATION RESPONSE HANDLER ---
async def invitee_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user selection for invitation."""
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
            await query.edit_message_text("This user is already invited to this meeting.")
            await sendMENU(update, context)
            return MENU

        AddInvite(meeting_id, inviter_id, invitee_id)

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT date, time, place FROM meetings WHERE id = ?", (meeting_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            await query.edit_message_text("Meeting not found.")
            return MENU

        date, time, place = row
        try:
            await context.bot.send_message(
                chat_id=invitee_id,
                text=f"You've been invited to a meeting 😍\n\n"
                     f"{format_date(date)} at {time},\n meeting place: {place} 🤯\n\n"
                     f"Are you coming? 🤨",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Yes, of course!✅", callback_data=f"accept_{meeting_id}_{invitee_id}"),
                     InlineKeyboardButton("No, I pass❌", callback_data=f"decline_{meeting_id}_{invitee_id}")]
                ])
            )
            await query.edit_message_text("Invitation sent!")
        except Exception as e:
            await query.edit_message_text(
                "Failed to send invitation. Possibly the user hasn't started the bot yet.\n"
                "Ask them to write /start, then try again."
            )

        await sendMENU(update, context)
        return MENU

    elif data == "menu":
        await sendMENU(update, context)
        return MENU


# --- CANCEL DIALOG ---
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current dialog with /cancel."""
    keyboard = [[exit_btn]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Okay, canceled your meeting.', reply_markup=reply_markup)
    return ConversationHandler.END


# --- ADMIN HANDLERS ---
async def adminreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user ID input for granting/revoking admin rights."""
    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Enter a valid numeric ID.")
        return ADMINLIST

    if user_exists(target_id):
        keyboard = [[InlineKeyboardButton("Open admin list", callback_data="adminlist")], [exit_btn]]
        keyboardm = [[exit_btn]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if check_admin(target_id):
            give_or_revoke_admin(target_id, 0)
            await update.message.reply_text('Admin rights revoked.', reply_markup=reply_markup)
            reply_markup = InlineKeyboardMarkup(keyboardm)
            await context.bot.send_message(chat_id=target_id, text="Your admin rights have been revoked.", reply_markup=reply_markup)
        else:
            give_or_revoke_admin(target_id, 1)
            await update.message.reply_text('Admin rights granted.', reply_markup=reply_markup)
            reply_markup = InlineKeyboardMarkup(keyboardm)
            await context.bot.send_message(chat_id=target_id, text="You've been granted admin rights!", reply_markup=reply_markup)
    else:
        keyboard = [[exit_btn]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=target_id, text="User not found. Check ID.", reply_markup=reply_markup)

    return ADMINLIST


async def adminlistreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin list."""
    query = update.callback_query
    await query.answer()
    admins = admin_list()
    text = "Admin list:\n\n"
    i = 0
    for adm in admins:
        fname, uname = get_name_from_user_id(adm[0])
        i += 1
        text += f"{i}. {fname} {uname} {adm[0]}\n\n"

    keyboard = [[InlineKeyboardButton("Grant/revoke admin rights", callback_data="admin")], [exit_btn]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_markup)
    return MENU


async def deletereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user ID input for deleting a user."""
    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Enter a valid numeric ID.")
        return MENU

    reply_markup = InlineKeyboardMarkup([[exit_btn], [InlineKeyboardButton("User list", callback_data="user")]])
    if user_exists(target_id):
        delete_user(target_id)
        await update.message.reply_text("User deleted.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("User does not exist. Check ID.", reply_markup=reply_markup)

    return MENU


async def cityreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle city input."""
    city = update.message.text.strip()
    if not city:
        await update.message.reply_text("Enter a valid city name.", reply_markup=InlineKeyboardMarkup([[exit_btn]]))
        return CITY

    update_city(update.message.from_user.id, city)
    await update.message.reply_text(f"City changed to {city}", reply_markup=InlineKeyboardMarkup([[exit_btn]]))
    return MENU


# --- MAIN ---
def main():
    """Initialize DB, create ConversationHandler, and start bot."""
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
    restore_reminders(app)   # restore reminders on startup
    print("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()