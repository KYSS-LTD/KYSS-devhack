import json
import os
import random
from typing import Any, List, Dict
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
        self.timeout = int(os.getenv("TIMEWEB_TIMEOUT", "60"))  # Увеличил таймаут для большого пака

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _validate_questions(self, questions: List[dict], count: int, used_texts: set) -> List[dict]:
        valid: List[dict] = []
        for item in questions:
            if not isinstance(item, dict): continue
            text = item.get("text")
            options = item.get("options", [])
            correct = item.get("correct_option")

            if not text or text in used_texts or not isinstance(options, list) or len(options) < 4:
                continue

            try:
                correct = int(correct)
                if correct not in [1, 2, 3, 4]: continue
            except:
                continue

            valid.append({"text": text, "options": options[:4], "correct_option": correct})
            used_texts.add(text)
            if len(valid) >= count: break

        return valid

    def generate_batch_questions(self, topic: str, total_count: int, used_texts: set, difficulty: str = "medium") -> List[dict]:
        """Генерирует сразу большое количество вопросов одним запросом."""
        # Явный промпт для JSON формата, чтобы нейросеть не ошибалась
        difficulty_hint = {
            "easy": "простого уровня: базовые факты и очевидные варианты",
            "medium": "среднего уровня: нужно базовое понимание темы",
            "hard": "сложного уровня: больше глубины и нетривиальных формулировок",
        }.get(difficulty, "среднего уровня")

        prompt = (
            f"Сгенерируй {total_count} уникальных вопросов для викторины по теме '{topic}' ни больше, ни меньше."
            f"со сложностью '{difficulty}' ({difficulty_hint}). "
        )

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "temperature": 0.6,  # Чуть выше, чтобы вопросы были разнообразнее
            "messages": [{"role": "user", "content": prompt}],
        }

        for attempt in range(3):
            try:
                print(f"📡 Запрос к AI: Генерация пака из {total_count} вопросов...")
                response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload,
                                         timeout=self.timeout)
                response.raise_for_status()

                content = response.json()["choices"][0]["message"]["content"].strip()
                if "```" in content:
                    content = content.split("```")[1].replace("json", "").strip()

                parsed = json.loads(content)
                if isinstance(parsed, dict) and "data" in parsed: parsed = parsed["data"]

                questions = self._validate_questions(parsed, total_count, used_texts)
                if len(questions) >= total_count:
                    return questions
                print(f"⚠️ Получено {len(questions)}/{total_count} валидных вопросов, пробую еще раз...")
            except Exception as e:
                print(f"❌ Ошибка генерации (попытка {attempt + 1}): {e}")

        # Если AI подвел, берем из фолбека
        print("🛟 Использую резервные вопросы")
        pool = [q for q in FALLBACK_QUESTIONS if q["text"] not in used_texts]
        random.shuffle(pool)
        return pool[:total_count]


def get_questions_for_teams(teams: List[str], topic: str, q_per_team: int = 2) -> Dict[str, List[dict]]:
    """
    Главная функция: делает 1 запрос и распределяет вопросы по командам.
    """
    client = TimewebClient()
    total_needed = len(teams) * q_per_team
    used_texts = set()

    # 1. Получаем общий список вопросов
    all_questions = client.generate_batch_questions(topic, total_needed, used_texts)

    # 2. Перемешиваем для пущей случайности
    random.shuffle(all_questions)

    # 3. Распределяем по командам
    team_assignments = {}
    for i, team in enumerate(teams):
        start_idx = i * q_per_team
        team_assignments[team] = all_questions[start_idx: start_idx + q_per_team]

    return team_assignments


def generate_questions(topic: str, count: int, used_texts: set = None, difficulty: str = "medium") -> List[dict]:
    """
    Генерирует пачку вопросов за один запрос.
    Используется как совместимый интерфейс для старого кода,
    но теперь работает через batch-метод.
    """
    if used_texts is None:
        used_texts = set()

    client = TimewebClient()
    # Пытаемся получить всё одним махом
    questions = client.generate_batch_questions(topic, count, used_texts, difficulty=difficulty)

    # Если вдруг AI выдал меньше, чем просили, добираем из заглушек
    if len(questions) < count:
        needed = count - len(questions)
        pool = [q for q in FALLBACK_QUESTIONS if q["text"] not in used_texts]
        random.shuffle(pool)
        questions.extend(pool[:needed])

    return questions[:count]
