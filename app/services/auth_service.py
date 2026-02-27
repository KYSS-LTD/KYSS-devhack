"""
Сервис аутентификации пользователей.

Обрабатывает регистрацию и вход пользователей в систему.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password, verify_password


class AuthService:
    """Сервис для управления аутентификацией пользователей."""


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
            raise HTTPException(status_code=400, detail="Имя пользователя уже занято")
        # Создание нового пользователя
        user = User(username=username, password_hash=hash_password(password))
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
        if not user:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

        valid, needs_rehash = verify_password(password, user.password_hash)
        if not valid:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

        if needs_rehash:
            user.password_hash = hash_password(password)
            db.add(user)
            db.commit()
            db.refresh(user)

        return user


# Экземпляр сервиса для использования в приложении
auth_service = AuthService()
