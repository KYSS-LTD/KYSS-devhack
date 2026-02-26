import json
import os
import random
from typing import Any, List
import requests
from dotenv import load_dotenv

load_dotenv()

FALLBACK_QUESTIONS = [
    {"text": "Что из перечисленного является языком программирования?", "options": ["HTTP", "Python", "SQLite", "CSS"],
     "correct_option": 2},
    {"text": "Какой протокол обычно используется для веб-сокетов?", "options": ["ws/wss", "ftp", "smtp", "ssh"],
     "correct_option": 1},
    {"text": "Что делает база данных SQLite?",
     "options": ["Рисует интерфейс", "Хранит данные", "Компилирует код", "Запускает браузер"], "correct_option": 2},
    {"text": "Какой HTTP-метод обычно используется для создания ресурса?", "options": ["GET", "PUT", "POST", "DELETE"],
     "correct_option": 3},
    {"text": "Что из этого относится к фронтенду?", "options": ["HTML", "SQL", "Linux kernel", "Docker image"],
     "correct_option": 1},
    {"text": "Какой из вариантов описывает FastAPI?",
     "options": ["Фреймворк Python", "IDE", "СУБД", "Операционная система"], "correct_option": 1},
    {"text": "Какой формат чаще всего используют для обмена данными в API?", "options": ["JPEG", "JSON", "MP3", "PDF"],
     "correct_option": 2},
]


class TimewebClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("TIMEWEB_API_KEY", "")
        self.api_base = os.getenv(
            "TIMEWEB_API_BASE",
            "https://agent.timeweb.cloud/api/v1/cloud-ai/agents/696c108a-b9f3-4c1b-ad84-bf2209a2168f/v1"
        )
        self.model = os.getenv("TIMEWEB_MODEL", "claude3.5")
        self.timeout = int(os.getenv("TIMEWEB_TIMEOUT", "40"))

    def is_configured(self) -> bool:
        if not self.api_key:
            print("⚠️  WARNING: TIMEWEB_API_KEY not set in environment variables")
            return False
        return True

    def _validate_questions(
            self, questions: List[dict[str, Any]], count: int, used_texts: set
    ) -> List[dict[str, Any]]:
        valid: List[dict[str, Any]] = []
        for item in questions:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            options = item.get("options", [])
            correct = item.get("correct_option")

            if not text or text in used_texts or not isinstance(options, list) or len(options) < 4:
                continue

            options = options[:4]

            try:
                correct = int(correct)
            except (ValueError, TypeError):
                continue

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
        prompt = f"Сгенерируй {count} уникальных вопросов для викторины по теме {topic}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "temperature": 0.5,
            "messages": [{"role": "user", "content": prompt}],
        }

        for attempt in range(3):
            try:
                print(f"\n📤 TIMEWEB API Request (Attempt {attempt + 1}/3):")
                print(f"   URL: {self.api_base}/chat/completions")
                print(f"   API Key: {self.api_key[:20]}{'...' if len(self.api_key) > 20 else ''}")

                response = requests.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

                print(f"   Status: {response.status_code}")

                if response.status_code == 401:
                    print("   ❌ Authentication failed (401)")
                    print("   Possible issues:")
                    print("      - TIMEWEB_API_KEY is empty or not set")
                    print("      - API key is invalid or expired")
                    print("      - Check your API key at https://timeweb.cloud")
                    raise Exception("Unauthorized - check API key")

                response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Удаляем markdown обертку если присутствует
                if content.startswith("```"):
                    content = content.split("```")[1].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()

                parsed = json.loads(content)

                # Если ответ не массив, попытаемся получить поле data
                if isinstance(parsed, dict) and "data" in parsed:
                    parsed = parsed["data"]

                if not isinstance(parsed, list):
                    parsed = [parsed]

                return self._validate_questions(parsed, count, used_texts)

            except Exception as e:
                print(f"TIMEWEB ATTEMPT {attempt + 1} FAILED: {e}")

        raise ValueError("AI не сгенерировал валидные вопросы после 3 попыток")


def generate_questions(topic: str, count: int, used_texts: set = None) -> List[dict[str, Any]]:
    if used_texts is None:
        used_texts = set()

    client = TimewebClient()
    if client.is_configured():
        try:
            return client.generate_questions(topic, count, used_texts)
        except Exception as e:
            print("Using fallback questions due to AI failure:", e)

    # Fallback — случайные уникальные вопросы из встроенного набора
    pool = [q for q in FALLBACK_QUESTIONS if q["text"] not in used_texts]
    random.shuffle(pool)
    selected = pool[:count]
    for q in selected:
        used_texts.add(q["text"])
    return selected