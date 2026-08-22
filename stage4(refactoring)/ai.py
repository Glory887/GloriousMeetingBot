# ai.py – Integration with OpenRouter (OpenAI-compatible API) for outfit advice

from openai import OpenAI
from config import OPENAI_API_KEY

async def get_ai(forecast, place):
    """
    Get AI-generated outfit advice based on weather forecast and meeting place.
    Uses OpenRouter API with GPT-3.5-turbo model.
    Returns a short practical recommendation or an error message.
    """
    if not OPENAI_API_KEY:
        return "⚠️ Нейросеть не настроена: отсутствует API-ключ."

    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты – стилист. Твоя задача – дать совет по одежде, "
                        "**обязательно используя предоставленные данные о погоде**. "
                        "Не домысливай, не пиши 'предположим', если в прогнозе есть конкретные цифры "
                        "(температура, ветер, осадки). Отвечай кратко, по делу (20-30 слов)."
                    )
                },
                {
                    "role": "user",
                    "content": f"Место встречи: {place}\n\nДанные о погоде (используй их для совета): {forecast}"
                }
            ],
            max_tokens=300,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Ошибка при обращении к нейросети: {e}"