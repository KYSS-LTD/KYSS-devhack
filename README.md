# QuizBattle (FastAPI + WebSockets + SQLite)

Полноценный прототип командной квиз-игры по ТЗ: backend на FastAPI, хранение в SQLite, WebSocket-реалтайм и базовый фронтенд (регистрация, вход, лобби, игра).

## Реализовано

- Регистрация и вход пользователей (`/register`, `/login` + API `/auth/*`)
- Главная страница создания комнаты и входа по PIN
- Отдельная страница профиля со статистикой игрока (`/profile`)
- Уникальный PIN (6 символов, буквы + цифры)
- Хранение игр/игроков/вопросов/пользователей в SQLite
- Лобби с разделением на 2 команды (A/B)
- Запуск игры только хостом
- Поочерёдные ходы команд
- 4 варианта ответа, подсчёт очков, победитель/ничья
- Таймер на вопрос (30 секунд)
- Обновления состояния в реальном времени через WebSocket
- Удаление игрока из игры при разрыве соединения
- Генерация вопросов через GigaChat + fallback при недоступности AI

## Запуск (Python 3.12)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Открыть: `http://127.0.0.1:8000`

## ENV для GigaChat

```bash
export GIGACHAT_AUTH_KEY=""
export GIGACHAT_SCOPE="GIGACHAT_API_PERS"
export GIGACHAT_MODEL="GigaChat"
export GIGACHAT_API_BASE="https://gigachat.devices.sberbank.ru/api/v1"
export GIGACHAT_AUTH_URL="https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
export GIGACHAT_VERIFY_SSL="false"
```

Если ключей нет или сервис недоступен, будут использованы запасные вопросы.

## Основные API

- `POST /auth/register`
- `POST /auth/login`
- `GET /users/{user_id}/stats`
- `POST /games`
- `POST /games/{pin}/join`
- `POST /games/{pin}/start`
- `GET /games/{pin}`
- `WS /ws/{pin}/{player_id}`

## Структура

```text
app/
  main.py
  database.py
  models.py
  schemas.py
  templates/
    login.html
    register.html
    index.html
    game.html
    profile.html
  static/
    css/style.css
    js/login.js
    js/register.js
    js/index.js
    js/game.js
    js/profile.js
  services/
    auth_service.py
    ai_service.py
    game_service.py
```
