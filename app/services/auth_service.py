"""
Сервис аутентификации пользователей.

Обрабатывает регистрацию и вход пользователей в систему.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User


class AuthService:
    """Сервис для управления аутентификацией пользователей."""

    def __init__(self) -> None:
        self._password_iterations = int(os.getenv("PASSWORD_HASH_ITERATIONS", "200000"))
        self._session_ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60 * 24 * 14)))
        self._secret_key = os.getenv("AUTH_SECRET_KEY", "change-me-in-production").encode("utf-8")

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            self._password_iterations,
        )
        encoded = base64.urlsafe_b64encode(digest).decode("utf-8")
        return f"pbkdf2_sha256${self._password_iterations}${salt}${encoded}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        if password_hash.startswith("pbkdf2_sha256$"):
            try:
                _, iterations_s, salt, expected = password_hash.split("$", 3)
                digest = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt.encode("utf-8"),
                    int(iterations_s),
                )
                actual = base64.urlsafe_b64encode(digest).decode("utf-8")
                return hmac.compare_digest(actual, expected)
            except Exception:
                return False

        legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy_hash, password_hash)

    def create_session_token(self, user_id: int) -> str:
        payload = {
            "sub": user_id,
            "exp": int(time.time()) + self._session_ttl_seconds,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=")
        signature = hmac.new(self._secret_key, payload_b64, hashlib.sha256).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")
        return f"{payload_b64.decode('utf-8')}.{signature_b64.decode('utf-8')}"

    def verify_session_token(self, token: str | None) -> int | None:
        if not token or "." not in token:
            return None
        payload_b64_s, signature_b64_s = token.split(".", 1)
        payload_b64 = payload_b64_s.encode("utf-8")
        expected_signature = hmac.new(self._secret_key, payload_b64, hashlib.sha256).digest()
        try:
            signature = base64.urlsafe_b64decode(signature_b64_s + "==")
            if not hmac.compare_digest(signature, expected_signature):
                return None
            payload_raw = base64.urlsafe_b64decode(payload_b64_s + "==")
            payload = json.loads(payload_raw.decode("utf-8"))
            exp = int(payload.get("exp", 0))
            if exp < int(time.time()):
                return None
            user_id = int(payload.get("sub"))
            return user_id if user_id > 0 else None
        except Exception:
            return None

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
        user = User(username=username, password_hash=self._hash_password(password))
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
        if not user or not self._verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверные учетные данные")
        if not user.password_hash.startswith("pbkdf2_sha256$"):
            user.password_hash = self._hash_password(password)
            db.commit()
        return user


# Экземпляр сервиса для использования в приложении
auth_service = AuthService()
