import requests
import zoneinfo
from datetime import datetime
from config import WEATHER_API_KEY

async def get_weather_for_meeting(city: str, date_str: str, time_str: str, lang: str = 'ru') -> str:
    """
    Возвращает прогноз погоды в городе на указанную дату и время.
    Если lang='en', время показывается в UTC, иначе в МСК.
    """
    try:
        params = {
            'q': city,
            'appid': WEATHER_API_KEY,
            'units': 'metric',
            'lang': 'ru' if lang == 'ru' else 'en'
        }
        response = requests.get("http://api.openweathermap.org/data/2.5/forecast", params=params)
        data = response.json()
        if data.get("cod") != "200":
            return f"❌ Error: {data.get('message', 'city not found')}" if lang == 'en' else f"❌ Ошибка: {data.get('message', 'город не найден')}"

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
            return "❌ Forecast not found." if lang == 'en' else "❌ Прогноз на это время не найден."

        temp = best["main"]["temp"]
        feels_like = best["main"]["feels_like"]
        description = best["weather"][0]["description"]
        humidity = best["main"]["humidity"]
        wind = best["wind"]["speed"]

        dt_utc = datetime.fromtimestamp(best["dt"])
        if lang == 'en':
            forecast_time = dt_utc.strftime("%Y-%m-%d %H:%M UTC")
        else:
            dt_moscow = dt_utc.replace(tzinfo=zoneinfo.ZoneInfo("UTC")).astimezone(zoneinfo.ZoneInfo("Europe/Moscow"))
            forecast_time = dt_moscow.strftime("%d.%m.%Y %H:%M")

        if lang == 'en':
            return (
                f"🌤️ Weather forecast in {city} for {forecast_time}:\n"
                f"🌡️ Temperature: {temp}°C (feels like {feels_like}°C)\n"
                f"☁️ {description.capitalize()}\n"
                f"💧 Humidity: {humidity}%\n"
                f"💨 Wind: {wind} m/s\n"
            )
        else:
            return (
                f"🌤️ Прогноз погоды в {city} на {forecast_time}:\n"
                f"🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)\n"
                f"☁️ {description.capitalize()}\n"
                f"💧 Влажность: {humidity}%\n"
                f"💨 Ветер: {wind} м/с\n"
            )
    except Exception as e:
        return f"⚠️ Error: {e}" if lang == 'en' else f"⚠️ Ошибка: {e}"