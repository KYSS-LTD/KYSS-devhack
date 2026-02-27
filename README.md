# QuizBattle — KYSS

QuizBattle — веб-игра для командной викторины в реальном времени: ведущий создаёт комнату, игроки заходят по PIN, делятся на команды и отвечают на вопросы.

- **Команда:** KYSS
- **Домен:** <https://quizbattle.kyssltd.ru>

## Стек
- FastAPI + Uvicorn
- WebSocket realtime
- HTML/CSS/JS + Jinja2
- SQLAlchemy + SQLite
- GigaChat API (с fallback-вопросами)
- Docker Compose + Nginx + Let's Encrypt

## Локальный запуск
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Docker запуск (app + nginx)
```bash
docker compose up -d --build app nginx
```

## SSL автоматизация (Let's Encrypt)

1. Укажите домен и email (можно через `.env`):
```bash
DOMAIN=quizbattle.kyssltd.ru
EMAIL=admin@kyssltd.ru
```

2. Первый выпуск сертификата:
```bash
./deploy/init-letsencrypt.sh
```

3. Продление сертификата вручную:
```bash
./deploy/renew-letsencrypt.sh
```

Рекомендация: поставить `renew-letsencrypt.sh` в cron/systemd timer (например 2 раза в день).

## Важные файлы деплоя
- `Dockerfile`
- `docker-compose.yml`
- `deploy/nginx/default.conf.template`
- `deploy/init-letsencrypt.sh`
- `deploy/renew-letsencrypt.sh`

## ENV для AI
```bash
GIGACHAT_AUTH_KEY=
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_MODEL=GigaChat
GIGACHAT_API_BASE=https://gigachat.devices.sberbank.ru/api/v1
GIGACHAT_AUTH_URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth
GIGACHAT_VERIFY_SSL=false
```

Если AI недоступен, используются резервные вопросы.

## Соответствие ТЗ (кратко)
- ✅ Создание/вход в комнату по PIN
- ✅ Lobby + авторазделение на команды
- ✅ Realtime-игра с таймером, очками и победителем
- ✅ WebSocket-коммуникация
- ✅ AI-вопросы + fallback
- ✅ Профили/рейтинг/адаптивность/сложность
- ✅ Docker + Nginx + SSL-автоматизация для домена
