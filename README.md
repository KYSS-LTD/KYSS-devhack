# QuizBattle Backend (FastAPI + WebSockets + SQLite)

Бэкенд для хакатон-проекта **QuizBattle** по ТЗ: создание командной квиз-игры в реальном времени с хранением данных в **SQLite** и генерацией вопросов через **GigaChat** (с запасными вопросами при недоступности AI).

## Что реализовано

- Создание игры с темой и количеством вопросов на команду (5/6/7)
- Уникальный 6-символьный PIN (буквы + цифры) для активных игр
- Состояния игры: `waiting`, `in_progress`, `finished`
- Подключение игроков по PIN + имени
- Автоматическое разделение игроков на 2 команды (A/B)
- Старт игры только хостом
- Поочерёдные вопросы для команд A/B
- Таймер на вопрос (30 секунд)
- 4 варианта ответа, учёт правильных ответов
- Реалтайм-обновления через WebSocket
- Подсчёт очков и определение победителя/ничьей
- Удаление игрока из игры при отключении WebSocket
- Хранение игровых данных в SQLite (`quizbattle.db`)

## Технологии

- Python 3.12
- FastAPI
- SQLAlchemy
- SQLite
- WebSockets
- Requests (для GigaChat API)

## Запуск

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Сервер стартует на `http://127.0.0.1:8000`.

## Переменные окружения для GigaChat

Если переменные не заданы или AI недоступен — автоматически используются запасные вопросы.

```bash
export GIGACHAT_AUTH_KEY="<base64_credentials_input_for_basic_auth>"
export GIGACHAT_SCOPE="GIGACHAT_API_PERS"
export GIGACHAT_MODEL="GigaChat"
export GIGACHAT_API_BASE="https://gigachat.devices.sberbank.ru/api/v1"
export GIGACHAT_AUTH_URL="https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
export GIGACHAT_VERIFY_SSL="false"
```

## API (основное)

### 1) Создать игру
`POST /games`

```json
{
  "host_name": "Teacher",
  "topic": "История России",
  "questions_per_team": 5
}
```

### 2) Присоединиться к игре
`POST /games/{pin}/join`

```json
{
  "name": "Student 1"
}
```

### 3) Запустить игру (только хост)
`POST /games/{pin}/start`

```json
{
  "host_player_id": 1
}
```

### 4) Получить состояние игры
`GET /games/{pin}`

### 5) WebSocket
`WS /ws/{pin}/{player_id}`

Событие от клиента:

```json
{
  "action": "answer",
  "option_index": 2
}
```

Сервер отправляет:

- `type: "state"` — актуальное состояние игры
- `type: "answer_result"` — результат ответа
- `type: "pong"` — ответ на ping

## Структура проекта

```text
app/
  main.py
  database.py
  models.py
  schemas.py
  services/
    ai_service.py
    game_service.py
requirements.txt
README.md
```
