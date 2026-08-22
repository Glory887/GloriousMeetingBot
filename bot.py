import config
import db
import webserver
import reminder
import threading
from telegram.ext import (
    Application,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from handlers import (
    start,
    buttonreceived,
    cityreceived,
    deletereceived,
    adminlistreceived,
    adminreceived,
    invitee_received,
    datereceived,
    timereceived,
    placereceived,
    commentreceived,
    cancel_conversation,
)


def main():
    db.init_db()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(buttonreceived),
        ],
        states={
            config.CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, cityreceived)],
            config.DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletereceived)],
            config.ADMINLIST: [CallbackQueryHandler(adminlistreceived)],
            config.ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, adminreceived)],
            config.INVITEE: [CallbackQueryHandler(invitee_received)],
            config.MENU: [CallbackQueryHandler(buttonreceived)],
            config.DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, datereceived)],
            config.TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, timereceived)],
            config.PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, placereceived)],
            config.COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, commentreceived)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
    )

    app = Application.builder().token(config.TOKEN).build()

    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(target=webserver.run_web_server, daemon=True)
    web_thread.start()

    app.add_handler(conv_handler)
    reminder.restore_reminders(app)

    print("Гойда, братья!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()