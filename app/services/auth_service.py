"""
Сервис аутентификации пользователей.

Обрабатывает регистрацию и вход пользователей в систему.
"""

import hashlib

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User


class AuthService:
    """Сервис для управления аутентификацией пользователей."""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Хэширование пароля с использованием SHA256.

        Аргументы:
            password (str): Пароль в открытом виде

        Возвращает:
            str: Хэш пароля
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def register(self, db: Session, username: str, password: str) -> User:
        """
        Регистрация нового пользователя.

        Аргументы:
            db (Session): Сессия базы данных
            username (str): Имя пользователя
            password (str): Пароль

        Возвращает:
            User: Объект зарегистрированного пользователя

        Выбрасывает:
            HTTPException: Если имя пользователя уже занято
        """
        # Проверка существования пользователя
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        # Создание нового пользователя
        user = User(username=username, password_hash=self.hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def login(self, db: Session, username: str, password: str) -> User:
        """
        Вход пользователя в систему.

        Аргументы:
            db (Session): Сессия базы данных
            username (str): Имя пользователя
            password (str): Пароль

        Возвращает:
            User: Объект пользователя

        Выбрасывает:
            HTTPException: При неверных учетных данных
        """
        # Поиск пользователя
        user = db.query(User).filter(User.username == username).first()
        # Проверка учетных данных
        if not user or user.password_hash != self.hash_password(password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return user


# Экземпляр сервиса для использования в приложении
auth_service = AuthService()
