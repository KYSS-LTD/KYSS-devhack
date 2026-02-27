from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite:///./quizbattle.db"

# Создание движка базы данных с оптимизацией для SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,  # Увеличенный таймаут ожидания блокировки (секунды)
    },
    poolclass=StaticPool,  # Используем статический пул для лучшей многопоточности
    echo=False,
)

# Оптимизация SQLite при подключении
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    # Включаем WAL режим (Write-Ahead Logging) для лучшей параллельности
    cursor.execute("PRAGMA journal_mode=WAL")
    # Увеличиваем размер кэша для лучшей производительности
    cursor.execute("PRAGMA cache_size=5000")
    # Используем NORMAL синхронизацию вместо FULL (баланс между безопасностью и скоростью)
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Увеличиваем размер page для оптимизации
    cursor.execute("PRAGMA page_size=4096")
    # Увеличиваем размер памяти для временных таблиц
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()

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