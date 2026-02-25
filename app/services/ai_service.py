import base64
import os
import random
import uuid
from typing import Any, List
import requests
from dotenv import load_dotenv
load_dotenv()

FALLBACK_QUESTIONS = [
    {"text": "Что из перечисленного является языком программирования?", "options": ["HTTP", "Python", "SQLite", "CSS"], "correct_option": 2},
    {"text": "Какой протокол обычно используется для веб-сокетов?", "options": ["ws/wss", "ftp", "smtp", "ssh"], "correct_option": 1},
    {"text": "Что делает база данных SQLite?", "options": ["Рисует интерфейс", "Хранит данные", "Компилирует код", "Запускает браузер"], "correct_option": 2},
    {"text": "Какой HTTP-метод обычно используется для создания ресурса?", "options": ["GET", "PUT", "POST", "DELETE"], "correct_option": 3},
    {"text": "Что из этого относится к фронтенду?", "options": ["HTML", "SQL", "Linux kernel", "Docker image"], "correct_option": 1},
    {"text": "Какой из вариантов описывает FastAPI?", "options": ["Фреймворк Python", "IDE", "СУБД", "Операционная система"], "correct_option": 1},
    {"text": "Какой формат чаще всего используют для обмена данными в API?", "options": ["JPEG", "JSON", "MP3", "PDF"], "correct_option": 2},
]

class GigaChatClient:
    def __init__(self) -> None:
        self.auth_key = os.getenv("GIGACHAT_AUTH_KEY", "")
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.model = os.getenv("GIGACHAT_MODEL", "GigaChat")
        self.api_base = os.getenv("GIGACHAT_API_BASE", "https://gigachat.devices.sberbank.ru/api/v1")
        self.auth_url = os.getenv("GIGACHAT_AUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth")
        self.verify_ssl = os.getenv("GIGACHAT_VERIFY_SSL", "true").lower() == "true"

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
        token = response.json().get("access_token")
        if not token:
            raise ValueError("No access_token in response")
        return token

    def _validate_questions(self, questions: List[dict[str, Any]], count: int, used_texts: set) -> List[dict[str, Any]]:
        valid: List[dict[str, Any]] = []
        for item in questions:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            options = item.get("options", [])
            correct = int(item.get("correct_option", 0))
            if not text or text in used_texts or not isinstance(options, list) or len(options) < 4:
                continue
            options = options[:4]
            if correct not in [1, 2, 3, 4]:
                continue
            valid.append({"text": text, "options": options, "correct_option": correct})
            used_texts.add(text)
            if len(valid) >= count:
                break
        if len(valid) < count:
            raise ValueError("Недостаточно валидных уникальных вопросов от AI")
        return valid

    def generate_questions(self, topic: str, count: int, used_texts: set) -> List[dict[str, Any]]:
        token = self._get_access_token()
        prompt = f"""
                Ты — генератор JSON.

                Сгенерируй РОВНО {count} уникальных вопросов для викторины по теме "{topic}".
                Не повторяй вопросы, которые уже есть в used_texts.

                Верни ТОЛЬКО JSON.
                Без пояснений.
                Без markdown.
                Без текста до или после.
                Без ```.

                Формат ответа — строго JSON-массив.

                Каждый элемент массива ОБЯЗАТЕЛЬНО должен иметь формат:

                {{
                  "text": "Текст вопроса",
                  "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
                  "correct_option": 1
                }}

                ТРЕБОВАНИЯ:
                - options содержит РОВНО 4 строки
                - ****ТОЛЬКО 4 ВАРИАНТА ОТВЕТА И ТОЛЬКО 1 ПРАВИЛЬНЫЙ****
                - correct_option — число 1, 2, 3 или 4
                - correct_option соответствует правильному варианту
                - все поля обязательны
                - никаких дополнительных полей
                - никаких комментариев
                - только валидный JSON

                Верни результат сейчас.
                """
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"model": self.model, "temperature": 0.5, "messages": [{"role": "user", "content": prompt}]},
                    timeout=40,
                    verify=self.verify_ssl,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("```")[1].strip()
                import json
                parsed = json.loads(content)
                return self._validate_questions(parsed, count, used_texts)
            except Exception as e:
                print(f"GIGACHAT ATTEMPT {attempt+1} FAILED:", e)
        raise ValueError("AI не сгенерировал валидные вопросы после 3 попыток")

def generate_questions(topic: str, count: int, used_texts: set = None) -> List[dict[str, Any]]:
    if used_texts is None:
        used_texts = set()

    client = GigaChatClient()
    if client.is_configured():
        try:
            return client.generate_questions(topic, count, used_texts)
        except Exception as e:
            print("Using fallback questions due to AI failure:", e)

    # fallback — уникальные вопросы
    pool = [q for q in FALLBACK_QUESTIONS if q["text"] not in used_texts]
    random.shuffle(pool)
    selected = pool[:count]
    for q in selected:
        used_texts.add(q["text"])
    return selected