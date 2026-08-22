from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    ContextTypes,
)
import config
import db
import sqlite3
from datetime import datetime
import zoneinfo
from utils import format_datetime_moscow
from reminder import send_meeting_reminder, get_remind_datetime
from ai import get_ai
from getweather import get_weather_for_meeting
from config import menu_btn  # ← импорт кнопки "Меню"


async def sendMENU(update_or_query, context):
    meeting_btn = InlineKeyboardButton("Назначить встречу", callback_data="meetings")
    list_btn = InlineKeyboardButton("Посмотреть список встреч", callback_data="lists")
    end_btn = InlineKeyboardButton("Завершить", callback_data="end")
    city_btn = InlineKeyboardButton("Изменить город", callback_data="city")

    if update_or_query.callback_query and update_or_query.callback_query.message:
        user_id = update_or_query.callback_query.from_user.id
    else:
        user_id = update_or_query.effective_user.id

    if user_id == config.main_admin:
        keyboard = [
            [meeting_btn],
            [list_btn],
            [city_btn],
            [end_btn],
            [InlineKeyboardButton("Список пользователей", callback_data="user")],
            [InlineKeyboardButton("Список администраторов", callback_data="adminlist")]
        ]
    elif db.check_admin(user_id):
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

    if data == "meetings":
        await query.edit_message_text(
            'Напиши, какого числа произойдет встреча (формат ДД.ММ.ГГГГ):\n\n'
            'Если передумаешь, пропиши /cancel'
        )
        return config.DATE

    elif data == "lists":
        user_id = query.from_user.id
        rows = db.get_all_meetings(user_id)
        meetings_count = 0

        for meeting_id in rows:
            meetings = db.get_meeting_info(meeting_id[0])
            if not meetings:
                db.delete_invite(meeting_id[0], user_id)
                continue

            for row in meetings:
                invite_btn = InlineKeyboardButton(
                    "Пригласить друга",
                    callback_data=f"invite_{row[0]}"
                )
                keyboard = [[invite_btn]]

                text = ""
                text += f"Дата: {format_datetime_moscow(row[1],row[2])}(По МСК)\n"
                text += f"Место: {row[3]}\n"
                text += f"Комментарий: {row[4]}\n\n"
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
                    text += "ℹ️ Для прогноза погоды укажите город в меню.\n\n"

                answers = db.get_all_status(row[0])
                count = 0
                for i in answers[0]:
                    uname, fname = db.get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} согласен✅\n"
                    count += 1
                for i in answers[1]:
                    uname, fname = db.get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} не ответил🤨\n"
                for i in answers[2]:
                    uname, fname = db.get_name_from_user_id(i[0])
                    name = f"{fname} ({uname})" if fname else uname
                    text += f"{name} отказался❌\n"

                if count == 0:
                    db.delete_meeting(row[0])
                    continue

                if count == 1 and db.get_status(row[0], user_id) == "accepted" or db.check_admin(user_id):
                    callback = f"delete_{row[0]}"
                    keyboard.append([InlineKeyboardButton("Отменить встречу", callback_data=callback)])

                callback = f"change_{row[0]}_{user_id}_{db.get_status(row[0], user_id)}"
                keyboard.append([InlineKeyboardButton("Изменить свой статус", callback_data=callback)])
                if city != "0" and city is not None:
                    callback = f"ai_{row[0]}_{user_id}"
                    keyboard.append([InlineKeyboardButton("Посмотреть совет от нейросети", callback_data=callback)])
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
        return config.MENU

    elif data.startswith("delete_"):
        meeting_id = int(data.split("_")[1])
        db.delete_meeting(meeting_id)
        text = "Встреча удалена."
        keyboard = [[menu_btn]]
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
        keyboard = [[menu_btn]]
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
            reply_markup=InlineKeyboardMarkup([[menu_btn]])
        )
        return config.MENU

    elif data.startswith("invite_"):
        meeting_id = int(data.split("_")[1])
        users = db.get_all_users()
        keyboard = [[menu_btn]]
        if not users:
            await query.edit_message_text(
                "Попроси друзей написать /start боту!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return config.MENU

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
            await query.edit_message_text("Ты принял приглашение!")
            if inviter_id:
                await context.bot.send_message(chat_id=inviter_id, text=f"Пользователь {name} принял приглашение!")
        else:
            status = "declined"
            await query.edit_message_text("Ты отказался от приглашения.")
            if inviter_id:
                await context.bot.send_message(chat_id=inviter_id, text=f"Пользователь {name} отказался от приглашения(")

        if inviter_id:
            db.update_status(meeting_id, user_id, status)
        else:
            await query.edit_message_text("Ошибка: приглашающий не найден. Статус не обновлён.")

        await sendMENU(update, context)
        return config.MENU

    elif data == "user":
        text = "Список всех пользователей:\n\n"
        user = db.get_all_users()
        i = 0
        for u in user:
            i += 1
            fname, uname, uid = u
            text += f"{i}. {fname} {uname} {uid}\n"
        keyboard = [[menu_btn], [InlineKeyboardButton("Удалить пользователя", callback_data="deleteuser")]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return config.MENU

    elif data.startswith("ai_"):
        parts = data.split("_")
        if len(parts) < 3:
            await query.edit_message_text("Ошибка в данных.")
            return config.MENU
        meeting_id, user_id = int(parts[1]), int(parts[2])
        rows = db.get_meeting_info(meeting_id)
        if not rows:
            await query.edit_message_text("Встреча не найдена.")
            return config.MENU
        row = rows[0]
        date, time, place = row[1], row[2], row[3]
        city = db.get_city(user_id)
        if not city or city == "0":
            advice = "⚠️ Сначала укажите свой город в меню."
        else:
            forecast = await get_weather_for_meeting(city, date, time)
            advice = await get_ai(forecast, place)
        keyboard = [[menu_btn]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=advice,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return config.MENU

    elif data == "deleteuser":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Введите ID пользователя")
        return config.DELETE

    elif data == "city":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Введите название города (на английском, например Moscow):")
        return config.CITY

    elif data == "admin":
        await context.bot.send_message(chat_id=query.message.chat_id, text="Введите ID пользователя")
        return config.ADMIN

    elif data == "adminlist":
        return config.ADMINLIST

    elif data == "menu":
        await sendMENU(update, context)
        return config.MENU

    elif data == "end":
        await query.edit_message_text("До встречи!")
        return ConversationHandler.END

    return config.MENU


async def datereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text
    try:
        dt_obj = datetime.strptime(raw, "%d.%m.%Y")
        context.user_data['date'] = dt_obj.strftime("%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Неверный формат, используй ДД.ММ.ГГГГ")
        return config.DATE
    await update.message.reply_text('Отлично, во сколько хочешь встретиться? (формат ЧЧ:ММ, время по МСК)')
    return config.TIME


async def timereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text.strip()

    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ, например 14:30"
        )
        return config.TIME

    date_str = context.user_data.get("date")
    moscow_tz = zoneinfo.ZoneInfo("Europe/Moscow")
    utc_tz = zoneinfo.ZoneInfo("UTC")

    dt_moscow = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt_moscow = dt_moscow.replace(tzinfo=moscow_tz)
    dt_utc = dt_moscow.astimezone(utc_tz)

    if dt_utc < datetime.now(utc_tz):
        await update.message.reply_text("❌ Эта дата и время уже прошли. Выберите будущее время.")
        return config.DATE

    context.user_data['date'] = dt_utc.strftime("%Y-%m-%d")
    context.user_data['time'] = dt_utc.strftime("%H:%M")

    keyboard = [[menu_btn]]
    city = db.get_city(update.message.from_user.id)
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
            text="Если хотите увидеть прогноз погоды для своего города на этот день – введите название города в главном меню."
        )

    await update.message.reply_text(
        'Какое прекрасное место станет вашей точкой встречи (лучше пиши с предлогом, например "в торговом центре")?'
    )
    return config.PLACE


async def placereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['place'] = update.message.text
    await update.message.reply_text('Желаешь ли ты оставить какой-либо комментарий?')
    return config.COMMENT


async def commentreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    date = context.user_data.get("date")
    time = context.user_data.get("time")
    place = context.user_data.get("place")
    comment = update.message.text

    meeting_id = db.save_meeting(chat_id, user_id, date, time, place, comment)
    db.AddInvite(meeting_id, user_id, user_id)
    db.update_status(meeting_id, user_id, "accepted")

    invite_btn = InlineKeyboardButton(
        "Пригласить друга",
        callback_data=f"invite_{meeting_id}"
    )
    keyboard = [[invite_btn], [menu_btn]]
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

    return config.MENU


async def invitee_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pick_"):
        parts = data.split("_")
        meeting_id = int(parts[1])
        invitee_id = int(parts[2])
        inviter_id = query.from_user.id

        existing = db.get_status(meeting_id, invitee_id)
        if existing is not None:
            await query.edit_message_text("Этот пользователь уже приглашён на эту встречу.")
            await sendMENU(update, context)
            return config.MENU

        db.AddInvite(meeting_id, inviter_id, invitee_id)

        conn = sqlite3.connect(config.DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT date, time, place FROM meetings WHERE id = ?", (meeting_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            await query.edit_message_text("Встреча не найдена.")
            return config.MENU

        date, time, place = row
        try:
            await context.bot.send_message(
                chat_id=invitee_id,
                text=f"Тебя пригласили на встречу 😍\n\n"
                     f"{format_datetime_moscow(date,time)},\n встреча намечается {place} 🤯\n"
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
        return config.MENU

    elif data == "menu":
        await sendMENU(update, context)
        return config.MENU


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[menu_btn]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Окей, отменил твою встречу', reply_markup=reply_markup)
    return ConversationHandler.END


async def adminreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введите корректный числовой ID.")
        return config.ADMINLIST

    if db.user_exists(user_id):
        keyboard = [[InlineKeyboardButton("Открыть список администраторов", callback_data="adminlist")], [menu_btn]]
        keyboardm = [[menu_btn]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if db.check_admin(user_id):
            db.give_or_revoke_admin(user_id, 0)
            await update.message.reply_text('Права администратора изъяты', reply_markup=reply_markup)
            reply_markup = InlineKeyboardMarkup(keyboardm)
            await context.bot.send_message(chat_id=user_id, text="Права администратора изъяты", reply_markup=reply_markup)
        else:
            db.give_or_revoke_admin(user_id, 1)
            await update.message.reply_text('Выданы права администратора', reply_markup=reply_markup)
            reply_markup = InlineKeyboardMarkup(keyboardm)
            await context.bot.send_message(chat_id=user_id, text="Выданы права администратора", reply_markup=reply_markup)
    else:
        keyboard = [[menu_btn]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text="Пользователь не найден, проверьте ID!", reply_markup=reply_markup)

    return config.ADMINLIST


async def adminlistreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin = db.admin_list()
    text = "Список админов:\n\n"
    i = 0
    for adm in admin:
        fname, uname = db.get_name_from_user_id(adm[0])
        i += 1
        text += f"{i}. {fname} {uname} {adm[0]}\n\n"

    keyboard = [[InlineKeyboardButton("Дать/забрать права администратора", callback_data="admin")], [menu_btn]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_markup)
    return config.MENU


async def deletereceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введите корректный числовой ID.")
        return config.MENU

    reply_markup = InlineKeyboardMarkup([[menu_btn], [InlineKeyboardButton("Список пользователей", callback_data="user")]])
    if db.user_exists(user_id):
        db.delete_user(user_id)
        await update.message.reply_text("Пользователь удален", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Пользователя не существует. Проверьте ID", reply_markup=reply_markup)

    return config.MENU


async def cityreceived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    if not city:
        await update.message.reply_text("Введите корректное название города", reply_markup=InlineKeyboardMarkup([[menu_btn]]))
        return config.CITY

    db.update_city(update.message.from_user.id, city)
    await update.message.reply_text(f"Город изменен на {city}", reply_markup=InlineKeyboardMarkup([[menu_btn]]))
    return config.MENU