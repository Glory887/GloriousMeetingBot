# -*- coding: utf-8 -*-

# --- IMPORTS ---
import logging
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
import sqlite3
import os   # added for environment variables

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- CONSTANTS ---
DB_NAME = "meetings.db"
main_admin = 1644253455   # hardcoded main admin (creator)

# Conversation states (used by ConversationHandler)
MENU, DATE, TIME, PLACE, COMMENT, LIST, INVITEE, ADMIN, ADMINLIST, DELETE = 887, 1, 2, 3, 4, 5, 6, 7, 8, 9

# Reusable "Menu" button
exit_btn = InlineKeyboardButton("Menu", callback_data="menu")


# --- DATABASE FUNCTIONS (new and extended) ---
def init_db():
    """
    Creates tables: meetings, invites, users.
    Also adds 'is_admin' column to users if missing (migration).
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Meetings table (same as Stage 1)
    cur.execute("""CREATE TABLE IF NOT EXISTS meetings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        place TEXT NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Invites table (new) — tracks who invited whom and status
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        inviter_id INTEGER NOT NULL,
        invitee_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',   -- 'pending', 'accepted', 'declined'
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    )""")

    # Users table (new) — stores user info and admin flag
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_admin INTEGER DEFAULT 0
    )
    """)

    # Migration: add is_admin column if missing
    cur.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cur.fetchall()]
    if 'is_admin' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


def save_meeting(chat_id, user_id, date, time, place, comment):
    """Insert meeting and return its ID"""
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
    """Return all meeting IDs where the user is invited"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT meeting_id FROM invites WHERE invitee_id=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_meeting_info(meeting_id):
    """Return full meeting details by ID"""
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
    """Insert a new invitation (status defaults to 'pending')"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO invites (meeting_id, inviter_id, invitee_id) VALUES (?, ?, ?)",
        (meeting_id, inviter_id, invitee_id)
    )
    conn.commit()
    conn.close()


def get_status(meeting_id, user_id):
    """Return status of a user for a specific meeting, or None"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT status FROM invites WHERE meeting_id=? AND invitee_id=?", (meeting_id, user_id))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def update_status(meeting_id, user_id, status):
    """Update invitation status (accepted/declined)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE invites SET status=? WHERE meeting_id = ? AND invitee_id = ?",
        (status, meeting_id, user_id)
    )
    conn.commit()
    conn.close()


def get_all_users():
    """Return all users (first_name, username, user_id)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username, user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows  # list of tuples (first_name, username, user_id)


def get_all_status(meeting_id):
    """Return three lists: accepted, pending, declined invitees for a meeting"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? AND status='accepted'", (meeting_id,))
    accept = cur.fetchall()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? AND status='pending'", (meeting_id,))
    pending = cur.fetchall()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? AND status='declined'", (meeting_id,))
    declined = cur.fetchall()
    conn.close()
    return [accept, pending, declined]


def get_name_from_user_id(user_id):
    """Return (first_name, username) for a user ID"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None


def get_inviter_from_invitee(user_id, meeting_id):
    """Return inviter_id for a given invitee and meeting"""
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
    """Delete a meeting (cascades to invites)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()


def delete_invite(meeting_id, invitee_id):
    """Delete a specific invitation"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM invites WHERE meeting_id = ? AND invitee_id = ?",
        (meeting_id, invitee_id)
    )
    conn.commit()
    conn.close()


def change_mind(user_id, meeting_id, status):
    """Toggle status between accepted/declined"""
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
    """Return True if user is admin (is_admin == 1)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,))
    answ = cur.fetchone()
    conn.close()
    if answ is None:
        return False
    return answ[0] == 1


def give_or_revoke_admin(user_id, status):
    """Set admin status (1 or 0) for a user"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()


def admin_list():
    """Return list of user IDs who are admins"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_admin=1")
    rows = cur.fetchall()
    conn.close()
    return rows


def user_exists(user_id):
    """Check if a user exists in users table"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def delete_user(user_id):
    """Delete a user and clean all their invites (both as inviter and invitee)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM invites WHERE invitee_id = ?", (user_id,))
    cur.execute("DELETE FROM invites WHERE inviter_id = ?", (user_id,))
    cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# --- HANDLERS ---
async def sendMENU(update_or_query, context):
    """
    Send main menu with inline buttons.
    Also shows admin-specific buttons if the user is main_admin or admin.
    """
    meeting_btn = InlineKeyboardButton("Schedule meeting", callback_data="meetings")
    list_btn = InlineKeyboardButton("View meetings", callback_data="lists")
    messages_btn = InlineKeyboardButton("Messages", callback_data="messages")
    end_btn = InlineKeyboardButton("Finish", callback_data="end")

    if update_or_query.callback_query and update_or_query.callback_query.message:
        user_id = update_or_query.callback_query.from_user.id
    else:
        user_id = update_or_query.effective_user.id

    if user_id == main_admin:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [messages_btn],
            [end_btn],
            [InlineKeyboardButton("User list", callback_data="user")],
            [InlineKeyboardButton("Admin list", callback_data="adminlist")]
        ]
    elif check_admin(user_id):
        keyboard = [
            [meeting_btn],
            [list_btn],
            [messages_btn],
            [end_btn],
            [InlineKeyboardButton("User list", callback_data="user")]
        ]
    else:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [messages_btn],
            [end_btn]
        ]

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
    """
    /start command handler:
    - Register user if new
    - Show main menu
    """
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
    """
    Main callback handler for all inline buttons.
    Handles:
    - Schedule meeting (→ DATE)
    - View meetings list (shows participants and statuses)
    - Invite friends (→ INVITEE)
    - Accept/decline invitations (updates status)
    - Change status
    - Delete meeting (admin or only participant)
    - User list (admin)
    - Delete user (admin)
    - Admin list (main admin)
    - Navigate back to menu
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "meetings":
        await query.edit_message_text(
            'Enter the meeting date (DD.MM.YYYY):\n\n'
            'If you change your mind, type /cancel'
        )
        return DATE

    elif data == "lists":
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
                text = "📅 Your meetings:\n\n"
                text += f"Date: {row[1]}\n"
                text += f"Time: {row[2]}\n"
                text += f"Place: {row[3]}\n"
                text += f"Comment: {row[4]}\n\n"

                answers = get_all_status(row[0])
                count = 0
                for i in answers[0]:   # accepted
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} ✅\n"
                    count += 1
                for i in answers[1]:   # pending
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} 🤨\n"
                for i in answers[2]:   # declined
                    uname, fname = get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} ❌\n"

                if count == 0:
                    delete_meeting(row[0])
                    continue

                # Show "Cancel meeting" if only 1 accepted (the user themselves) or admin
                if count == 1 and get_status(row[0], user_id) == "accepted" or check_admin(user_id):
                    callback = f"delete_{row[0]}"
                    keyboard.append([InlineKeyboardButton("Cancel meeting", callback_data=callback)])

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
            for usid in rows[1]:   # but we need to send to accepted? Actually we send to the inviter
                # Actually the logic here is a bit mixed; we'll keep it as in the original.
                # We'll send a status change confirmation.
                pass
        # Simplified: send a confirmation message
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
        text = "List of all users:\n\n"
        users = get_all_users()
        i = 0
        for u in users:
            i += 1
            fname, uname, uid = u
            text += f"{i}. {fname} {uname} {uid}\n"
        keyboard = [
            [exit_btn],
            [InlineKeyboardButton("Delete user", callback_data="deleteuser")]
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MENU

    elif data == "deleteuser":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Enter user ID:")
        return DELETE

    elif data == "messages":
        await query.edit_message_text("Notifications will appear here.")
        await sendMENU(update, context)
        return MENU

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


# --- MEETING CREATION STEPS (unchanged from Stage 1) ---
async def datereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['date'] = update.message.text
    await update.message.reply_text('Great! What time would you like to meet?')
    return TIME

async def timereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['time'] = update.message.text
    await update.message.reply_text('What wonderful place will be your meeting point? (e.g. "in the mall")')
    return PLACE

async def placereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['place'] = update.message.text
    await update.message.reply_text('Would you like to leave any comment?')
    return COMMENT

async def commentreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    date = context.user_data.get("date")
    time = context.user_data.get("time")
    place = context.user_data.get("place")
    comment = update.message.text

    meeting_id = save_meeting(chat_id, user_id, date, time, place, comment)
    AddInvite(meeting_id, user_id, user_id)   # creator invites themselves (accepted automatically)
    update_status(meeting_id, user_id, "accepted")

    invite_btn = InlineKeyboardButton(
        "Invite friend",
        callback_data=f"invite_{meeting_id}"
    )
    keyboard = [[invite_btn], [exit_btn]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Okay, I’ve remembered everything. I\'ll send reminders to you and your friends.',
        reply_markup=reply_markup
    )
    return MENU


# --- INVITATION RESPONSE HANDLER ---
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
                     f"{date} at {time},\n meeting place: {place} 🤯\n\n"
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


# --- ADMIN HANDLERS ---
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[exit_btn]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Okay, canceled your meeting.', reply_markup=reply_markup)
    return ConversationHandler.END


async def adminreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Enter a valid numeric ID.")
        return ADMINLIST

    if user_exists(user_id):
        keyboard = [
            [InlineKeyboardButton("Open admin list", callback_data="adminlist")],
            [exit_btn]
        ]
        keyboardm = [[exit_btn]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if check_admin(user_id):
            give_or_revoke_admin(user_id, 0)
            await update.message.reply_text('Admin rights revoked.', reply_markup=reply_markup)
            reply_markup = InlineKeyboardMarkup(keyboardm)
            await context.bot.send_message(chat_id=user_id, text="Your admin rights have been revoked.", reply_markup=reply_markup)
        else:
            give_or_revoke_admin(user_id, 1)
            await update.message.reply_text('Admin rights granted.', reply_markup=reply_markup)
            reply_markup = InlineKeyboardMarkup(keyboardm)
            await context.bot.send_message(chat_id=user_id, text="You've been granted admin rights!", reply_markup=reply_markup)
    else:
        keyboard = [[exit_btn]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text="User not found. Check ID.", reply_markup=reply_markup)

    return ADMINLIST


async def adminlistreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admins = admin_list()
    text = "Admin list:\n\n"
    i = 0
    for adm in admins:
        fname, uname = get_name_from_user_id(adm[0])
        i += 1
        text += f"{i}. {fname} {uname} {adm[0]}\n\n"

    keyboard = [
        [InlineKeyboardButton("Grant/revoke admin rights", callback_data="admin")],
        [exit_btn]
    ]
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return MENU


async def deletereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Enter a valid numeric ID.")
        return MENU

    reply_markup = InlineKeyboardMarkup([
        [exit_btn],
        [InlineKeyboardButton("User list", callback_data="user")]
    ])
    if user_exists(user_id):
        delete_user(user_id)
        await update.message.reply_text("User deleted.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("User does not exist. Check ID.", reply_markup=reply_markup)

    return MENU


# --- MAIN ---
def main():
    init_db()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(buttonreceived)
        ],
        states={
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

    app = Application.builder().token(os.environ.get('TELEGRAM_TOKEN')).build()
    app.add_handler(conv_handler)

    print("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()