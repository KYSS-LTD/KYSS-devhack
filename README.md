# QuizBattle — KYSS

QuizBattle — веб-игра для командной викторины в реальном времени: ведущий создаёт комнату, игроки заходят по PIN, делятся на две команды и соревнуются по очкам.

- **Команда:** KYSS
- **Проект:** QuizBattle
- **Прод-домен:** <https://quizbattle.kyssltd.ru>

---

## 1) О проекте

Проект реализует хакатонное ТЗ для игры «QuizBattle»:
- создание комнаты с темой и количеством вопросов;
- вход игроков по PIN;
- лобби с распределением по командам;
- игровой экран с таймером, вопросами и очками;
- realtime-обновления через WebSocket;
- AI-генерация вопросов с fallback на резервные.

---

## 2) Технологии

- **Backend:** FastAPI, SQLAlchemy, Uvicorn
- **Realtime:** WebSocket
- **Frontend:** HTML, CSS, JavaScript, Jinja2 templates
- **AI:** интеграция с AI + резервные вопросы при ошибках
- **Инфраструктура:** Docker, Docker Compose, Nginx

---

## 3) Запуск локально (без Docker)

### Требования
- Python 3.12+

### Команды

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Приложение будет доступно на: <http://127.0.0.1:8000>

---

## 4) Запуск в Docker (Nginx + FastAPI)

### Что добавлено
- `Dockerfile` для приложения
- `docker-compose.yml` с сервисами:
  - `app` (FastAPI/Uvicorn)
  - `nginx` (reverse proxy + WebSocket proxy)
- `deploy/nginx/default.conf` для проксирования HTTP и WS
- том `quizbattle_data` для сохранения SQLite базы

### Команды

```bash
docker compose up -d --build
```

Проверка:

```bash
docker compose ps
curl -I http://127.0.0.1/
```

Остановка:

```bash
docker compose down
```

---

## 5) Переменные окружения (AI)

Если ключи не заданы или AI недоступен, приложение автоматически использует fallback-вопросы.

```bash
TIMEWEB_API_KEY="enter_your_key"
TIMEWEB_API_BASE=https://agent.timeweb.cloud/api/v1/cloud-ai/agents/696c108a-b9f3-4c1b-ad84-bf2209a2168f/v1
TIMEWEB_MODEL=grok-4-fast
TIMEWEB_TIMEOUT=40
```

Для Docker можно создать `.env` рядом с `docker-compose.yml`.

### Security env-переменные

Для безопасной эксплуатации в production добавьте:

```bash
AUTH_SECRET_KEY="long-random-secret"
SESSION_TTL_SECONDS=1209600
PASSWORD_HASH_ITERATIONS=200000
SECURE_COOKIES=true
CORS_ALLOW_ORIGINS="https://quizbattle.kyssltd.ru"
```

---

## 6) Реализация относительно ТЗ

Ниже — статус реализации пунктов из технического задания.

### 6.1 Основной функционал

- ✅ Главная страница: вход по PIN и нику, создание новой игры
- ✅ При создании: тема вопросов, количество вопросов
- ✅ Генерация уникального PIN (6 символов, буквы+цифры)
- ✅ Состояния игры: ожидание / идёт / завершена
- ✅ Lobby: PIN, список игроков, авто-распределение по 2 командам
- ✅ Кнопка старта только у ведущего
- ✅ Одновременный переход игроков в игровой режим (через realtime обновления)
- ✅ Поочередные вопросы для команд
- ✅ Отображение, какая команда сейчас отвечает
- ✅ Таймер вопроса
- ✅ 4 варианта ответа
- ✅ Блокировка/обработка действий после финального ответа
- ✅ Подсчёт очков в реальном времени
- ✅ Определение победителя/ничьей
- ✅ Backend на Python (FastAPI)
- ✅ Realtime на WebSockets
- ✅ HTML/CSS/JS интерфейс
- ⚠️ Хранение данных: используется SQLite (в ТЗ базово указана оперативная память, а это не очень стабильно)
- ✅ Удаление игрока при отключении

### 6.2 Дополнительный функционал (nice to have)

- ✅ AI-генерация вопросов
- ✅ Fallback-вопросы при ошибках AI
- ✅ Адаптивность под мобильные устройства
- ✅ Выбор сложности вопросов
- ✅ Пауза/возобновление таймера ведущим
- ✅ Пропуск вопроса
- ✅ Регистрация и профили пользователей
- ✅ Рейтинг игроков

---

## 7) Основные маршруты

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /users/{user_id}/stats`
- `POST /games`
- `POST /games/{pin}/join`
- `POST /games/{pin}/start`
- `GET /games/{pin}`
- `WS /ws/{pin}/{player_id}`

---

## 8) Структура проекта

```text
app/
  main.py
  routers.py
  services/
    ai_service.py
    auth_service.py
    game_service.py
  templates/
  static/
deploy/
  nginx/
    default.conf
Dockerfile
docker-compose.yml
README.md
```

---

## 9) Команда

**KYSS**
- Backend, realtime, AI интеграция
- Frontend/UI
- DevOps/деплой и инфраструктура
