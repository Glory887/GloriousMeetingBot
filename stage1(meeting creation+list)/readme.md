# Stage 1: Basic Meeting Bot
This is the **first version** of a Telegram bot for organizing meetings with friends.  
It implements core functionality: creating meetings, storing them in a database, and viewing a list.

---

## 🎯 Features

- ✅ Create a meeting (date, time, place, comment)
- ✅ Save meetings to SQLite
- ✅ View all your meetings in a list
- ✅ Simple inline keyboard navigation
- ✅ Cancel meeting creation with `/cancel`

---

## 🧰 Technologies

| Tool | Purpose |
|------|---------|
| **Python 3.10+** | Core language |
| **python-telegram-bot** | Telegram Bot API wrapper |
| **SQLite3** | Embedded database |
| **logging** | Runtime logging |

---

## 🏗️ Architecture

- **Single-file structure** — all code in `bot.py` 
- **ConversationHandler** — step‑by‑step meeting creation
- **SQLite** — persistent storage
- **Inline keyboards** — navigation and commands

