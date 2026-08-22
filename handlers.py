from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, ContextTypes
import config
import db
import sqlite3
from datetime import datetime
import zoneinfo
from utils import format_datetime_moscow
from reminder import send_meeting_reminder, get_remind_datetime
from ai import get_ai
from getweather import get_weather_for_meeting
from i18n import get_text
from db import get_user_lang, set_user_lang


async def sendMENU(update_or_query, context):
    # Определяем user_id
    if update_or_query.callback_query and update_or_query.callback_query.message:
        user_id = update_or_query.callback_query.from_user.id
    else:
        user_id = update_or_query.effective_user.id

    lang = get_user_lang(user_id)

    # Кнопки с текстами из JSON
    meeting_btn = InlineKeyboardButton(get_text(lang, 'meeting_btn'), callback_data="meetings")
    list_btn = InlineKeyboardButton(get_text(lang, 'list_btn'), callback_data="lists")
    city_btn = InlineKeyboardButton(get_text(lang, 'city_btn'), callback_data="city")
    end_btn = InlineKeyboardButton(get_text(lang, 'end_btn'), callback_data="end")
    lang_btn = InlineKeyboardButton(get_text(lang, 'change_lang'), callback_data="switch_lang")

    if user_id == config.main_admin:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn],
            [InlineKeyboardButton(get_text(lang, 'user_list'), callback_data="user")],
            [InlineKeyboardButton(get_text(lang, 'admin_list'), callback_data="adminlist")],
            [lang_btn]
        ]
    elif db.check_admin(user_id):
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn],
            [InlineKeyboardButton(get_text(lang, 'user_list'), callback_data="user")],
            [lang_btn]
        ]
    else:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn],
            [lang_btn]
        ]

    if update_or_query.callback_query and update_or_query.callback_query.message:
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        chat_id = update_or_query.effective_chat.id

    await context.bot.send_message(
        chat_id=chat_id,
        text=get_text(lang, 'main_menu'),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    conn = sqlite3.connect(config.DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
        (user_id, first_name, username)
    )
    conn.commit()
    conn.close()
    await sendMENU(update, context)
    return config.MENU


async def buttonreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = get_user_lang(user_id)

    if data == "meetings":
        await query.edit_message_text(
            get_text(lang, 'ask_date') + "\n\n" + get_text(lang, 'cancel_hint')
        )
        return config.DATE

    elif data == "lists":
        rows = db.get_all_meetings(user_id)
        meetings_count = 0

        for meeting_id in rows:
            meetings = db.get_meeting_info(meeting_id[0])
            if not meetings:
                db.delete_invite(meeting_id[0], user_id)
                continue

            for row in meetings:
                invite_btn = InlineKeyboardButton(
                    get_text(lang, 'invite_friend'),
                    callback_data=f"invite_{row[0]}"
                )
                keyboard = [[invite_btn]]

                text = ""
                # Используем ключи из вашего JSON – добавьте в JSON ключи date_label, place_label, comment_label
                text += f"📅 {get_text(lang, 'date_label')}: {format_datetime_moscow(row[1], row[2])} (МСК)\n"
                text += f"📍 {get_text(lang, 'place_label')}: {row[3]}\n"
                text += f"💬 {get_text(lang, 'comment_label')}: {row[4]}\n\n"

                try:
                    meeting_datetime = datetime.strptime(f"{row[1]} {row[2]}", "%Y-%m-%d %H:%M")
                except ValueError:
                    db.delete_meeting(row[0])
                    continue

                if meeting_datetime < datetime.now():
                    db.delete_meeting(row[0])
                    continue

                city = db.get_city(user_id)
                if city:
                    weather_text = await get_weather_for_meeting(city, row[1], row[2])
                    text += weather_text + "\n\n"
                else:
                    # Используем city_hint (добавьте в JSON)
                    text += get_text(lang, 'city_hint') + "\n\n"

                answers = db.get_all_status(row[0])
                count = 0
                for i in answers[0]:
                    uname, fname = db.get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} ✅\n"
                    count += 1
                for i in answers[1]:
                    uname, fname = db.get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} 🤨\n"
                for i in answers[2]:
                    uname, fname = db.get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} ❌\n"

                if count == 0:
                    db.delete_meeting(row[0])
                    continue

                if count == 1 and db.get_status(row[0], user_id) == "accepted" or db.check_admin(user_id):
                    callback = f"delete_{row[0]}"
                    keyboard.append([InlineKeyboardButton(get_text(lang, 'cancel_meeting'), callback_data=callback)])

                callback = f"change_{row[0]}_{user_id}_{db.get_status(row[0], user_id)}"
                keyboard.append([InlineKeyboardButton(get_text(lang, 'change_status'), callback_data=callback)])

                if city != "0" and city is not None:
                    callback = f"ai_{row[0]}_{user_id}"
                    keyboard.append([InlineKeyboardButton(get_text(lang, 'ai_advice'), callback_data=callback)])

                meetings_count += 1

                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        if not meetings_count:
            await context.bot.send_message(chat_id=query.message.chat_id, text=get_text(lang, 'no_meetings'))

        await sendMENU(update, context)
        return config.MENU

    elif data.startswith("delete_"):
        meeting_id = int(data.split("_")[1])
        db.delete_meeting(meeting_id)
        text = get_text(lang, 'deleted')
        keyboard = [[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return config.MENU

    elif data.startswith("change_"):
        parts = data.split("_")
        meeting_id = int(parts[1])
        user_id = int(parts[2])
        status = parts[3]
        db.change_mind(user_id, meeting_id, status)
        rows = db.get_all_status(meeting_id)
        users = db.get_name_from_user_id(user_id)
        fname, uname = users
        keyboard = [[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]]
        label = f"{fname} ({uname})" if fname else uname or str(user_id)

        if status == "accepted":
            for usid in rows[0]:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=get_text(lang, 'rejected_user'),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await context.bot.send_message(
                    chat_id=usid[0],
                    text=f"{label} {get_text(lang, 'rejected_owner')}"
                )
        else:
            for usid in rows[0]:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=get_text(lang, 'agreed_user'),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await context.bot.send_message(
                    chat_id=usid[0],
                    text=f"{label} {get_text(lang, 'agreed_owner')}"
                )

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=get_text(lang, 'status_changed'),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]])
        )
        return config.MENU

    elif data.startswith("invite_"):
        meeting_id = int(data.split("_")[1])
        users = db.get_all_users()
        if not users:
            await query.edit_message_text(
                get_text(lang, 'no_users'),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]])
            )
            return config.MENU

        keyboard = []
        for fname, uname, uid in users:
            label = f"{fname} ({uname})" if fname else uname or str(uid)
            callback = f"pick_{meeting_id}_{uid}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback)])
        keyboard.append([InlineKeyboardButton(get_text(lang, 'cancel'), callback_data="menu")])

        await query.edit_message_text(
            get_text(lang, 'choose_person'),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return config.INVITEE

    elif data.startswith("accept_") or data.startswith("decline_"):
        parts = data.split("_")
        user_id = int(parts[2])
        meeting_id = int(parts[1])
        uname, fname = db.get_name_from_user_id(user_id)
        name = f"{fname} ({uname})" if fname else uname
        inviter_id = db.get_inviter_from_invitee(user_id, meeting_id)

        if data.startswith("accept_"):
            status = "accepted"
            await query.edit_message_text(get_text(lang, 'agreed_user'))
            if inviter_id:
                await context.bot.send_message(chat_id=inviter_id, text=f"{name} {get_text(lang, 'agreed_owner')}")
        else:
            status = "declined"
            await query.edit_message_text(get_text(lang, 'rejected_user'))
            if inviter_id:
                await context.bot.send_message(chat_id=inviter_id, text=f"{name} {get_text(lang, 'rejected_owner')}")

        if inviter_id:
            db.update_status(meeting_id, user_id, status)
        else:
            await query.edit_message_text(get_text(lang, 'invite_fail'))

        await sendMENU(update, context)
        return config.MENU

    elif data == "switch_lang":
        current = get_user_lang(user_id)
        new = 'en' if current == 'ru' else 'ru'
        set_user_lang(user_id, new)
        await sendMENU(update, context)
        return config.MENU

    elif data == "user":
        text = get_text(lang, 'user_list') + "\n\n"
        users = db.get_all_users()
        for i, (fname, uname, uid) in enumerate(users, 1):
            text += f"{i}. {fname} {uname} (ID: {uid})\n"
        keyboard = [
            [InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")],
            [InlineKeyboardButton(get_text(lang, 'delete_user'), callback_data="deleteuser")]
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return config.MENU

    elif data.startswith("ai_"):
        parts = data.split("_")
        if len(parts) < 3:
            await query.edit_message_text(get_text(lang, 'error_data'))
            return config.MENU
        meeting_id, user_id = int(parts[1]), int(parts[2])
        rows = db.get_meeting_info(meeting_id)
        if not rows:
            await query.edit_message_text(get_text(lang, 'meeting_not_found'))
            return config.MENU
        row = rows[0]
        date, time, place = row[1], row[2], row[3]
        city = db.get_city(user_id)
        if not city or city == "0":
            advice = get_text(lang, 'ai_advice_hint')
        else:
            forecast = await get_weather_for_meeting(city, date, time)
            advice = await get_ai(forecast, place)
        keyboard = [[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=advice,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return config.MENU

    elif data == "deleteuser":
        await context.bot.send_message(chat_id=query.message.chat_id, text=get_text(lang, 'enter_id'))
        return config.DELETE

    elif data == "city":
        await context.bot.send_message(chat_id=query.message.chat_id, text=get_text(lang, 'enter_city'))
        return config.CITY

    elif data == "admin":
        await context.bot.send_message(chat_id=query.message.chat_id, text=get_text(lang, 'enter_id'))
        return config.ADMIN

    elif data == "adminlist":
        return config.ADMINLIST

    elif data == "menu":
        await sendMENU(update, context)
        return config.MENU

    elif data == "end":
        await query.edit_message_text(get_text(lang, 'end'))
        return ConversationHandler.END

    return config.MENU


async def datereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    raw = update.message.text
    try:
        dt_obj = datetime.strptime(raw, "%d.%m.%Y")
        context.user_data['date'] = dt_obj.strftime("%Y-%m-%d")
    except ValueError:
        await update.message.reply_text(get_text(lang, 'date_error'))
        return config.DATE
    await update.message.reply_text(get_text(lang, 'ask_time'))
    return config.TIME


async def timereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    time_str = update.message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text(get_text(lang, 'time_error'))
        return config.TIME

    date_str = context.user_data.get("date")
    moscow_tz = zoneinfo.ZoneInfo("Europe/Moscow")
    utc_tz = zoneinfo.ZoneInfo("UTC")

    dt_moscow = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt_moscow = dt_moscow.replace(tzinfo=moscow_tz)
    dt_utc = dt_moscow.astimezone(utc_tz)

    if dt_utc < datetime.now(utc_tz):
        await update.message.reply_text(get_text(lang, 'past_time'))
        return config.DATE

    context.user_data['date'] = dt_utc.strftime("%Y-%m-%d")
    context.user_data['time'] = dt_utc.strftime("%H:%M")

    keyboard = [[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]]
    city = db.get_city(user_id)
    if city:
        weather = await get_weather_for_meeting(city, context.user_data['date'], context.user_data['time'])
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=weather,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=get_text(lang, 'city_hint')
        )

    await update.message.reply_text(get_text(lang, 'ask_place'))
    return config.PLACE


async def placereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    context.user_data['place'] = update.message.text
    await update.message.reply_text(get_text(lang, 'ask_comment'))
    return config.COMMENT


async def commentreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    lang = get_user_lang(user_id)
    date = context.user_data.get("date")
    time = context.user_data.get("time")
    place = context.user_data.get("place")
    comment = update.message.text

    meeting_id = db.save_meeting(chat_id, user_id, date, time, place, comment)
    db.AddInvite(meeting_id, user_id, user_id)
    db.update_status(meeting_id, user_id, "accepted")

    invite_btn = InlineKeyboardButton(
        get_text(lang, 'invite_friend'),
        callback_data=f"invite_{meeting_id}"
    )
    keyboard = [[invite_btn], [InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(get_text(lang, 'saved'), reply_markup=reply_markup)

    # Напоминания
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

    return config.MENU


async def invitee_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = get_user_lang(user_id)

    if data.startswith("pick_"):
        parts = data.split("_")
        meeting_id = int(parts[1])
        invitee_id = int(parts[2])
        inviter_id = user_id

        existing = db.get_status(meeting_id, invitee_id)
        if existing is not None:
            await query.edit_message_text(get_text(lang, 'already_invited'))
            await sendMENU(update, context)
            return config.MENU

        db.AddInvite(meeting_id, inviter_id, invitee_id)

        conn = sqlite3.connect(config.DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT date, time, place FROM meetings WHERE id = ?", (meeting_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            await query.edit_message_text(get_text(lang, 'meeting_not_found'))
            return config.MENU

        date, time, place = row
        try:
            await context.bot.send_message(
                chat_id=invitee_id,
                text=(
                    get_text(lang, 'invited1') +
                    f"{format_datetime_moscow(date, time)},\n" +
                    f"{get_text(lang, 'invited2')} {place} {get_text(lang, 'invited3')}"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(get_text(lang, 'agree'), callback_data=f"accept_{meeting_id}_{invitee_id}"),
                        InlineKeyboardButton(get_text(lang, 'discard'), callback_data=f"decline_{meeting_id}_{invitee_id}")
                    ]
                ])
            )
            await query.edit_message_text(get_text(lang, 'invite_sent'))
        except Exception as e:
            await query.edit_message_text(get_text(lang, 'invite_fail'))

        await sendMENU(update, context)
        return config.MENU

    elif data == "menu":
        await sendMENU(update, context)
        return config.MENU


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    keyboard = [[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]]
    await update.message.reply_text(get_text(lang, 'meeting_canceled'), reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END


async def adminreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(get_text(lang, 'enter_id_correct'))
        return config.ADMINLIST

    if db.user_exists(target_id):
        keyboard = [
            [InlineKeyboardButton(get_text(lang, 'admin_list'), callback_data="adminlist")],
            [InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]
        ]
        keyboardm = [[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if db.check_admin(target_id):
            db.give_or_revoke_admin(target_id, 0)
            await update.message.reply_text(get_text(lang, 'taken_rights'), reply_markup=reply_markup)
            await context.bot.send_message(chat_id=target_id, text=get_text(lang, 'taken_rights'), reply_markup=InlineKeyboardMarkup(keyboardm))
        else:
            db.give_or_revoke_admin(target_id, 1)
            await update.message.reply_text(get_text(lang, 'got_rights'), reply_markup=reply_markup)
            await context.bot.send_message(chat_id=target_id, text=get_text(lang, 'got_rights'), reply_markup=InlineKeyboardMarkup(keyboardm))
    else:
        keyboard = [[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]]
        await context.bot.send_message(chat_id=target_id, text=get_text(lang, 'user_not_found'), reply_markup=InlineKeyboardMarkup(keyboard))

    return config.ADMINLIST


async def adminlistreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    admins = db.admin_list()
    text = get_text(lang, 'admin_list') + "\n\n"
    for i, adm in enumerate(admins, 1):
        fname, uname = db.get_name_from_user_id(adm[0])
        text += f"{i}. {fname} {uname} (ID: {adm[0]})\n"

    keyboard = [
        [InlineKeyboardButton(get_text(lang, 'give/take_rights'), callback_data="admin")],
        [InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]
    ]
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return config.MENU


async def deletereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(get_text(lang, 'enter_id_correct'))
        return config.MENU

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")],
        [InlineKeyboardButton(get_text(lang, 'user_list'), callback_data="user")]
    ])
    if db.user_exists(target_id):
        db.delete_user(target_id)
        await update.message.reply_text(get_text(lang, 'user_deleted'), reply_markup=reply_markup)
    else:
        await update.message.reply_text(get_text(lang, 'user_not_exists'), reply_markup=reply_markup)

    return config.MENU


async def cityreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    city = update.message.text.strip()
    if not city:
        await update.message.reply_text(
            get_text(lang, 'enter_city_correct'),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]])
        )
        return config.CITY

    db.update_city(user_id, city)
    await update.message.reply_text(
        f"{get_text(lang, 'city_changed')} {city}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, 'menu_btn'), callback_data="menu")]])
    )
    return config.MENU