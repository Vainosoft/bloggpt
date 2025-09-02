import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
import requests

app = FastAPI()

# API ключи из переменных окружения
openai.api_key = os.getenv("OPENAI_API_KEY")
currentsapi_key = os.getenv("CURRENTS_API_KEY")

if not openai.api_key or not currentsapi_key:
    raise ValueError("OPENAI_API_KEY и CURRENTS_API_KEY должны быть установлены")

MAX_TELEGRAM_LENGTH = 4096  # Лимит Telegram

class Topic(BaseModel):
    topic: str

# Получение новостей по теме
def get_recent_news(topic: str):
    url = "https://api.currentsapi.services/v1/latest-news"
    params = {
        "language": "en",
        "keywords": topic,
        "category": "health,technology",
        "apiKey": currentsapi_key
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении данных: {response.text}")

    news_data = response.json().get("news", [])
    if not news_data:
        return "Свежих новостей не найдено."

    return "\n".join([article["title"] for article in news_data[:5]])

# Генерация контента
def generate_content(topic: str):
    recent_news = get_recent_news(topic)

    try:
        # Заголовок
        title = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Придумайте привлекательный заголовок строго по теме '{topic}', с учётом новостей:\n{recent_news}"
            }],
            max_tokens=60,
            temperature=0.5
        ).choices[0].message.content.strip()

        # Мета-описание
        meta_description = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Напишите краткое и ёмкое мета-описание для статьи с заголовком '{title}', строго по теме '{topic}'."
            }],
            max_tokens=100,
            temperature=0.5
        ).choices[0].message.content.strip()

        # Тело статьи
        prompt = f"""Напишите статью строго по теме: '{topic}', используя свежие новости:
{recent_news}

Требования:
1. Максимальная длина — 4000 символов.
2. Структура: вступление, основная часть, заключение.
3. Используйте подзаголовки и конкретику.
4. Убирайте "воду" и вводные фразы.
5. Статья должна быть логичной и легко читаемой."""

        post_content = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{ "role": "user", "content": prompt }],
            max_tokens=1000,
            temperature=0.5,
            presence_penalty=0.6,
            frequency_penalty=0.6
        ).choices[0].message.content.strip()

        # Финальный текст для Telegram
        full_text = f"*{title}*\n\n{meta_description}\n\n{post_content}"
        if len(full_text) > MAX_TELEGRAM_LENGTH:
            full_text = full_text[:MAX_TELEGRAM_LENGTH - 3].rstrip() + "..."

        return {
            "title": title,
            "meta_description": meta_description,
            "post_content": full_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при генерации контента: {str(e)}")

# API
@app.post("/generate-post")
async def generate_post_api(topic: Topic):
    return generate_content(topic.topic)

@app.get("/")
async def root():
    return {"message": "Service is running"}

@app.get("/heartbeat")
async def heartbeat_api():
    return {"status": "OK"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
