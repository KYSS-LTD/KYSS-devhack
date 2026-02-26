"""
Основной файл приложения QuizBattle.

Содержит настройку FastAPI приложения, подключение базы данных,
настройку CORS и регистрацию маршрутов.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)
