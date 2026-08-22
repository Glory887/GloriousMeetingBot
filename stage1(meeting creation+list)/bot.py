# -*- coding: utf-8 -*-

# --- IMPORTS ---
import logging
import sqlite3
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

# --- LOGGING SETUP ---
# Print logs to console with timestamp, level, and module name
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- CONSTANTS ---
DB_NAME = "meetings.db"  # SQLite database file

# Conversation states (used by ConversationHandler)
MENU, DATE, TIME, PLACE, COMMENT = 887, 1, 2, 3, 4
# MENU = 887 is the main menu, others are steps for creating a meeting

# Reusable button and keyboard
exit_btn = InlineKeyboardButton("Menu", callback_data="menu")
keyboard_menu = [[exit_btn]]  # keyboard with a single "Menu" button


# --- DATABASE FUNCTIONS ---
def init_db():
    """Create the meetings table if it doesn't exist"""
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()


def save_meeting(chat_id, user_id, date, time, place, comment):
    """Insert a new meeting into the database"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO meetings (chat_id, user_id, date, time, place, comment)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (chat_id, user_id, date, time, place, comment))
    conn.commit()
    conn.close()


def get_meeting(user_id):
    """Return all meetings where the user is involved (by user_id)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, date, time, place, comment, created_at FROM meetings WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# --- HANDLERS ---
async def sendMENU(update_or_query, context):
    """
    Send the main menu with inline buttons.
    Works both for /start command and for callback queries.
    """
    meeting_btn = InlineKeyboardButton("Schedule meeting", callback_data="meetings")
    list_btn = InlineKeyboardButton("View meetings", callback_data="lists")
    messages_btn = InlineKeyboardButton("Messages", callback_data="messages")
    end_btn = InlineKeyboardButton("Finish", callback_data="end")

    keyboard = [
        [meeting_btn],
        [list_btn],
        [messages_btn],
        [end_btn]
    ]

    await context.bot.send_message(
        chat_id=update_or_query.effective_chat.id,
        text="Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command. Shows main menu."""
    await sendMENU(update, context)
    return MENU


async def buttonreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main handler for all inline button clicks.
    Processes callback_data and performs corresponding actions.
    """
    query = update.callback_query
    await query.answer()  # always respond to callback to remove loading indicator
    data = query.data

    if data == "meetings":
        # Button "Schedule meeting" → ask for date
        await query.edit_message_text(
            'Enter the meeting date:\n\n'
            'If you change your mind, type /cancel'
        )
        return DATE

    elif data == "lists":
        # Button "View meetings"
        user_id = query.from_user.id
        meetings = get_meeting(user_id)
        text = "📅 Your meetings:\n\n"

        if not meetings:
            # No meetings → show message and "Menu" button
            await query.edit_message_text(
                "You have no saved meetings yet.",
                reply_markup=InlineKeyboardMarkup(keyboard_menu)
            )
        else:
            # Format the list of meetings
            for row in meetings:
                text += f"Date: {row[1]}\n"
                text += f"Time: {row[2]}\n"
                text += f"Place: {row[3]}\n"
                text += f"Comment: {row[4]}\n\n\n"
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard_menu)
            )

        # After viewing the list, return to main menu
        await sendMENU(update, context)
        return MENU

    elif data == "messages":
        # Placeholder for "Messages" section
        await query.edit_message_text("Notifications will appear here.")
        await sendMENU(update, context)
        return MENU

    elif data == "menu":
        # "Menu" button → go back to main menu
        await sendMENU(update, context)
        return MENU

    elif data == "end":
        # "Finish" → end the conversation
        await query.edit_message_text("See you later!")
        return ConversationHandler.END

    return MENU  # fallback for unknown data


# --- MEETING CREATION STEPS ---
async def datereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive date, store in context.user_data, ask for time."""
    context.user_data['date'] = update.message.text
    await update.message.reply_text('Great! What time would you like to meet?')
    return TIME


async def timereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive time, store, ask for place."""
    context.user_data['time'] = update.message.text
    await update.message.reply_text('What wonderful place will be your meeting point?')
    return PLACE


async def placereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive place, store, ask for comment."""
    context.user_data['place'] = update.message.text
    await update.message.reply_text('Would you like to leave any comment?')
    return COMMENT


async def commentreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive comment, save meeting to DB, finish dialog, return to menu."""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    date = context.user_data.get("date")
    time = context.user_data.get("time")
    place = context.user_data.get("place")
    comment = update.message.text

    save_meeting(chat_id, user_id, date, time, place, comment)

    await update.message.reply_text(
        'Okay, I’ve remembered and recorded everything. I’ll send reminders to you and your friends.'
    )
    await sendMENU(update, context)
    return MENU


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current dialog with /cancel command."""
    await update.message.reply_text('Okay, canceled your meeting.')
    return ConversationHandler.END


# --- MAIN FUNCTION ---
def main():
    init_db()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(buttonreceived)
        ],
        states={
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