import base64
import os
import random
import uuid
from typing import Any

import requests

FALLBACK_QUESTIONS = [
    {
        "text": "Что из перечисленного является языком программирования?",
        "options": ["HTTP", "Python", "SQLite", "CSS"],
        "correct_option": 2,
    },
    {
        "text": "Какой протокол обычно используется для веб-сокетов?",
        "options": ["ws/wss", "ftp", "smtp", "ssh"],
        "correct_option": 1,
    },
    {
        "text": "Что делает база данных SQLite?",
        "options": ["Рисует интерфейс", "Хранит данные", "Компилирует код", "Запускает браузер"],
        "correct_option": 2,
    },
    {
        "text": "Какой HTTP-метод обычно используется для создания ресурса?",
        "options": ["GET", "PUT", "POST", "DELETE"],
        "correct_option": 3,
    },
    {
        "text": "Что из этого относится к фронтенду?",
        "options": ["HTML", "SQL", "Linux kernel", "Docker image"],
        "correct_option": 1,
    },
    {
        "text": "Какой из вариантов описывает FastAPI?",
        "options": ["Фреймворк Python", "IDE", "СУБД", "Операционная система"],
        "correct_option": 1,
    },
    {
        "text": "Какой формат чаще всего используют для обмена данными в API?",
        "options": ["JPEG", "JSON", "MP3", "PDF"],
        "correct_option": 2,
    },
]


class GigaChatClient:
    def __init__(self) -> None:
        self.auth_key = os.getenv("GIGACHAT_AUTH_KEY", "")
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.model = os.getenv("GIGACHAT_MODEL", "GigaChat")
        self.api_base = os.getenv("GIGACHAT_API_BASE", "https://gigachat.devices.sberbank.ru/api/v1")
        self.auth_url = os.getenv("GIGACHAT_AUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth")
        self.verify_ssl = os.getenv("GIGACHAT_VERIFY_SSL", "false").lower() == "true"

    def is_configured(self) -> bool:
        return bool(self.auth_key)

    def _get_access_token(self) -> str:
        encoded = base64.b64encode(self.auth_key.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {encoded}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(
            self.auth_url,
            headers=headers,
            data={"scope": self.scope},
            timeout=20,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def generate_questions(self, topic: str, count: int) -> list[dict[str, Any]]:
        token = self._get_access_token()
        prompt = (
            "Сгенерируй вопросы для викторины. Верни только JSON-массив без markdown. "
            f"Тема: {topic}. Количество: {count}. "
            "Формат каждого элемента: "
            '{"text":"...","options":["...","...","...","..."],"correct_option":1..4}. '
            "correct_option — номер правильного ответа от 1 до 4."
        )

        response = requests.post(
            f"{self.api_base}/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": 0.5,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=40,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        import json

        parsed = json.loads(content)
        valid: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            options = item.get("options", [])
            correct = int(item.get("correct_option", 0))
            if isinstance(options, list) and len(options) == 4 and 1 <= correct <= 4:
                valid.append(
                    {
                        "text": str(item.get("text", "")),
                        "options": [str(v) for v in options],
                        "correct_option": correct,
                    }
                )
        if len(valid) < count:
            raise ValueError("Недостаточно валидных вопросов от AI")
        return valid[:count]


def generate_questions(topic: str, count: int) -> list[dict[str, Any]]:
    client = GigaChatClient()
    if client.is_configured():
        try:
            return client.generate_questions(topic, count)
        except Exception:
            pass

    pool = FALLBACK_QUESTIONS.copy()
    random.shuffle(pool)
    result = []
    for i in range(count):
        item = pool[i % len(pool)]
        result.append(item)
    return result
