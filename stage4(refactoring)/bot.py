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
    # Initialize the database (creates tables if missing)
    db.init_db()

    # Build the ConversationHandler with all dialog states
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

    # Create the bot application using the token from config
    app = Application.builder().token(config.TOKEN).build()

    # Start a background web server for health checks (required for Render)
    web_thread = threading.Thread(target=webserver.run_web_server, daemon=True)
    web_thread.start()

    # Add the conversation handler to the app
    app.add_handler(conv_handler)

    # Restore scheduled reminders from the database
    reminder.restore_reminders(app)

    print("Бот запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()