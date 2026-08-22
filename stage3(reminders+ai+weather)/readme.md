# Stage 3: Weather Forecast & Reminders

This stage adds:

- **Weather forecast** – shows weather for meeting time using OpenWeatherMap API.
- **Automatic reminders** – users receive notifications 48h, 24h, 2h, and 1h before each meeting.
- **User city** – users can store their city to get personalized weather.
- **Weather displayed** in meeting list and during creation.

---

## 🆕 What's New in Stage 3

| Feature | Description |
|---------|-------------|
| 🌤️ **Weather forecast** | Integrated OpenWeatherMap API; shows temperature, wind, humidity for meeting time |
| 🏙️ **User city** | Users can set their city via the "Change city" button to see forecast|
| ⏰ **Reminders** | 4 automatic reminders (48h, 24h, 2h, 1h before meeting) |
| 📊 **Weather in list** | Meeting list shows weather forecast for each upcoming meeting |
| 🔄 **Reminder restoration** | Reminders persist after bot restart (saved in DB) |

---

## 🧰 Technologies

- **Python 3.10+**
- **python-telegram-bot**
- **SQLite3**
- **OpenWeatherMap API**
- **requests**
- **datetime, timedelta**
- **locale** (for Russian month names)

---