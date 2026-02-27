"""
Основной файл приложения QuizBattle.

Содержит настройку FastAPI приложения, подключение базы данных,
настройку CORS и регистрацию маршрутов.
"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from app.routers import router as main_router
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Создает таблицы в базе данных при запуске приложения.
    """
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="QuizBattle Backend",
    version="1.2.0",
    description="Backend для игры QuizBattle - викторины в реальном времени",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

cors_origins_env = os.getenv("QUIZBATTLE_CORS_ORIGINS", "")
allow_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

# Для локальной разработки: разрешаем localhost/127.0.0.1 с любым портом.
# Это закрывает 403 на WebSocket из браузера, где Origin обычно включает порт.
allow_origin_regex = os.getenv(
    "QUIZBATTLE_CORS_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(main_router)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "connect-src 'self' ws: wss:; "
        "font-src 'self' data:; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    return response
