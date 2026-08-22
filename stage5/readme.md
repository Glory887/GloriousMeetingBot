# Stage 5: Internationalization & Timezone Support

This stage adds full multilingual support and proper timezone handling.

---

## 🆕 What's New in Stage 5

| Feature | Description |
|---------|-------------|
| 🌍 **Multi‑language support** | Full Russian and English localization using JSON translation files |
| 🔄 **Language switching** | Users can switch languages via a button in the main menu |
| 🕒 **Timezone‑aware** | Dates shown in **MSK** for Russian, **UTC** for English |
| 📁 **i18n module** | `i18n.py` loads translations from JSON files with caching |
| 📋 **Localized messages** | All user‑facing texts (buttons, errors, notifications) are translatable |
| 💾 **User preference** | Language choice is stored per user in the database |

---

## 🧰 Technologies

- **Python 3.10+**
- **python-telegram-bot**
- **SQLite3**
- **JSON** (translation files)
- **zoneinfo**, **datetime** (timezone conversion)

---