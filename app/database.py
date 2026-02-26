from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./quizbattle.db"

# Создание движка базы данных
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Создание локальной сессии базы данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей SQLAlchemy
Base = declarative_base()


def get_db():
    """
    Получение сессии базы данных.

    Возвращает:
        Generator[SessionLocal, None, None]: Генератор сессии базы данных
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
