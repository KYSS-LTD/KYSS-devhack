"""Утилиты безопасности: подпись токенов, хэширование паролей, cookie-настройки."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

from fastapi import HTTPException


DEFAULT_SECRET = "dev-insecure-secret-change-me"
PBKDF2_ITERATIONS = 210_000


def _secret_key() -> bytes:
    return os.getenv("QUIZBATTLE_SECRET_KEY", DEFAULT_SECRET).encode("utf-8")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64d(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload: str) -> str:
    sig = hmac.new(_secret_key(), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64e(sig)


def _secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@dataclass(frozen=True)
class CookieSettings:
    secure: bool
    samesite: str


def get_cookie_settings() -> CookieSettings:
    https_only = os.getenv("QUIZBATTLE_HTTPS_ONLY", "0") == "1"
    return CookieSettings(secure=https_only, samesite="lax")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, password_hash: str) -> tuple[bool, bool]:
    """Вернет (is_valid, needs_rehash). Поддерживает legacy SHA256."""
    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iters_raw, salt_raw, digest_raw = password_hash.split("$", 3)
            iterations = int(iters_raw)
            salt = _b64d(salt_raw)
            expected = _b64d(digest_raw)
        except (ValueError, TypeError):
            return False, False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        valid = hmac.compare_digest(actual, expected)
        return valid, valid and iterations < PBKDF2_ITERATIONS

    # Legacy sha256 fallback
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    valid_legacy = hmac.compare_digest(legacy, password_hash)
    return valid_legacy, valid_legacy


def create_user_session_token(user_id: int, ttl_seconds: int = 60 * 60 * 24 * 7) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"u:{user_id}:{exp}"
    return f"{payload}.{_sign(payload)}"


def verify_user_session_token(token: str | None) -> int:
    if not token:
        raise HTTPException(status_code=401, detail="Не аутентифицирован")
    try:
        payload, sig = token.rsplit(".", 1)
        kind, user_id_raw, exp_raw = payload.split(":", 2)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Невалидная сессия") from exc

    if kind != "u" or not _secure_compare(_sign(payload), sig):
        raise HTTPException(status_code=401, detail="Невалидная сессия")

    if int(exp_raw) < int(time.time()):
        raise HTTPException(status_code=401, detail="Сессия истекла")

    return int(user_id_raw)


def create_player_token(pin: str, player_id: int, ttl_seconds: int = 60 * 60 * 8) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"p:{pin.upper()}:{player_id}:{exp}"
    return f"{payload}.{_sign(payload)}"


def verify_player_token(pin: str, player_id: int, token: str | None) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Нужен токен игрока")
    try:
        payload, sig = token.rsplit(".", 1)
        kind, signed_pin, signed_player_id_raw, exp_raw = payload.split(":", 3)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Невалидный токен игрока") from exc

    if kind != "p" or not _secure_compare(_sign(payload), sig):
        raise HTTPException(status_code=401, detail="Невалидный токен игрока")

    if signed_pin != pin.upper() or int(signed_player_id_raw) != player_id:
        raise HTTPException(status_code=403, detail="Токен игрока не подходит")

    if int(exp_raw) < int(time.time()):
        raise HTTPException(status_code=401, detail="Токен игрока истек")
