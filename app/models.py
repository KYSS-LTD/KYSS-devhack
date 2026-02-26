"""
Модели данных для приложения QuizBattle.

Определяет структуру данных для пользователей, игр, игроков и вопросов,
используя SQLAlchemy ORM.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    """
    Модель пользователя.

    Атрибуты:
        id (int): Уникальный идентификатор пользователя
        username (str): Уникальное имя пользователя
        password_hash (str): Хэш пароля пользователя
        created_at (datetime): Дата и время создания пользователя
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Game(Base):
    """
    Модель игры.

    Атрибуты:
        id (int): Уникальный идентификатор игры
        pin (str): Уникальный 6-символьный код для подключения к игре
        topic (str): Тема игры
        questions_per_team (int): Количество вопросов на команду
        status (str): Статус игры (waiting, in_progress, finished)
        current_team (str): Текущая команда, которая отвечает на вопрос
        current_index_a (int): Индекс текущего вопроса для команды A
        current_index_b (int): Индекс текущего вопроса для команды B
        score_a (int): Счет команды A
        score_b (int): Счет команды B
        created_at (datetime): Дата и время создания игры
    """

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pin: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    topic: Mapped[str] = mapped_column(String(255))
    questions_per_team: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="waiting")
    current_team: Mapped[str | None] = mapped_column(String(1), nullable=True)
    current_index_a: Mapped[int] = mapped_column(Integer, default=0)
    current_index_b: Mapped[int] = mapped_column(Integer, default=0)
    score_a: Mapped[int] = mapped_column(Integer, default=0)
    score_b: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    players: Mapped[list["Player"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class Player(Base):
    """
    Модель игрока.

    Атрибуты:
        id (int): Уникальный идентификатор игрока
        game_id (int): Идентификатор игры, к которой принадлежит игрок
        user_id (int): Идентификатор пользователя (если зарегистрирован)
        name (str): Имя игрока
        team (str): Команда игрока (A или B)
        is_host (bool): Является ли игрок хостом игры
        active (bool): Активен ли игрок в игре
        joined_at (datetime): Дата и время присоединения к игре
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    team: Mapped[str] = mapped_column(String(1))
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    game: Mapped[Game] = relationship(back_populates="players")


class Question(Base):
    """
    Модель вопроса.

    Атрибуты:
        id (int): Уникальный идентификатор вопроса
        game_id (int): Идентификатор игры, к которой принадлежит вопрос
        team (str): Команда, которой предназначен вопрос (A или B)
        order_index (int): Порядковый номер вопроса в команде
        text (str): Текст вопроса
        option_1 (str): Первый вариант ответа
        option_2 (str): Второй вариант ответа
        option_3 (str): Третий вариант ответа
        option_4 (str): Четвертый вариант ответа
        correct_option (int): Номер правильного варианта ответа (1-4)
        answered (bool): Был ли вопрос отвечен
    """

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    team: Mapped[str] = mapped_column(String(1), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    option_1: Mapped[str] = mapped_column(String(255))
    option_2: Mapped[str] = mapped_column(String(255))
    option_3: Mapped[str] = mapped_column(String(255))
    option_4: Mapped[str] = mapped_column(String(255))
    correct_option: Mapped[int] = mapped_column(Integer)
    answered: Mapped[bool] = mapped_column(Boolean, default=False)

    # Связи
    game: Mapped[Game] = relationship(back_populates="questions")
