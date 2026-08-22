import zoneinfo
from db import WEATHER_API_KEY
import requests
from datetime import datetime
async def get_weather_for_meeting(city: str, date_str: str, time_str: str) -> str:
    """
    Возвращает прогноз погоды в городе на указанную дату и время.
    date_str: "YYYY-MM-DD", time_str: "HH:MM"
    """
    try:
        params = {
    'q': city,
    'appid': WEATHER_API_KEY,
    'units': 'metric',
    'lang': 'ru'
}
        response = requests.get("http://api.openweathermap.org/data/2.5/forecast", params=params)
        data = response.json()
        if data.get("cod") != "200":
            return f"❌ Ошибка: {data.get('message', 'город не найден')}"

        meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        meeting_ts = int(meeting_dt.timestamp())

        best = None
        best_diff = float('inf')
        for forecast in data["list"]:
            diff = abs(forecast["dt"] - meeting_ts)
            if diff < best_diff:
                best_diff = diff
                best = forecast

        if best is None:
            return "❌ Прогноз на это время не найден."

        temp = best["main"]["temp"]
        feels_like = best["main"]["feels_like"]
        description = best["weather"][0]["description"]
        humidity = best["main"]["humidity"]
        wind = best["wind"]["speed"]

        dt_utc = datetime.fromtimestamp(best["dt"])
        dt_moscow = dt_utc.replace(tzinfo=zoneinfo.ZoneInfo("UTC")).astimezone(zoneinfo.ZoneInfo("Europe/Moscow"))
        forecast_time = dt_moscow.strftime("%d.%m.%Y %H:%M")
        return (
            f"🌤️ Прогноз погоды в {city} на {forecast_time}:\n"
            f"🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)\n"
            f"☁️ {description.capitalize()}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind} м/с\n"
        )
    except Exception as e:
        return f"⚠️ Ошибка при получении прогноза: {e}"