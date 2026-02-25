from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Game(Base):
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

    players: Mapped[list["Player"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    questions: Mapped[list["Question"]] = relationship(back_populates="game", cascade="all, delete-orphan")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    team: Mapped[str] = mapped_column(String(1))
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    game: Mapped[Game] = relationship(back_populates="players")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    team: Mapped[str] = mapped_column(String(1), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    option_1: Mapped[str] = mapped_column(String(255))
    option_2: Mapped[str] = mapped_column(String(255))
    option_3: Mapped[str] = mapped_column(String(255))
    option_4: Mapped[str] = mapped_column(String(255))
    correct_option: Mapped[int] = mapped_column(Integer)
    answered: Mapped[bool] = mapped_column(Boolean, default=False)

    game: Mapped[Game] = relationship(back_populates="questions")
