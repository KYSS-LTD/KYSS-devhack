"""Утилиты безопасности: JWT, хэширование паролей, cookie-настройки."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any

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


def _secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _jwt_sign(unsigned_token: str) -> str:
    sig = hmac.new(_secret_key(), unsigned_token.encode("utf-8"), hashlib.sha256).digest()
    return _b64e(sig)


def _jwt_encode(claims: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64e(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64e(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    unsigned = f"{header_b64}.{payload_b64}"
    return f"{unsigned}.{_jwt_sign(unsigned)}"


def _jwt_decode(token: str | None) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=401, detail="Не аутентифицирован")

    try:
        header_b64, payload_b64, signature = token.split(".", 2)
        unsigned = f"{header_b64}.{payload_b64}"
        expected_sig = _jwt_sign(unsigned)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Невалидный токен") from exc

    if not _secure_compare(expected_sig, signature):
        raise HTTPException(status_code=401, detail="Невалидный токен")

    try:
        header = json.loads(_b64d(header_b64).decode("utf-8"))
        payload = json.loads(_b64d(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Невалидный токен") from exc

    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise HTTPException(status_code=401, detail="Невалидный токен")

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise HTTPException(status_code=401, detail="Токен истек")

    return payload


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

    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    valid_legacy = hmac.compare_digest(legacy, password_hash)
    return valid_legacy, valid_legacy


def create_user_session_token(user_id: int, ttl_seconds: int = 60 * 60 * 24 * 7) -> str:
    now = int(time.time())
    claims = {
        "typ": "session",
        "sub": str(user_id),
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return _jwt_encode(claims)


def verify_user_session_token(token: str | None) -> int:
    payload = _jwt_decode(token)
    if payload.get("typ") != "session":
        raise HTTPException(status_code=401, detail="Невалидная сессия")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise HTTPException(status_code=401, detail="Невалидная сессия")

    return int(sub)


def create_player_token(pin: str, player_id: int, ttl_seconds: int = 60 * 60 * 8) -> str:
    now = int(time.time())
    claims = {
        "typ": "player",
        "pin": pin.upper(),
        "pid": player_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return _jwt_encode(claims)


def verify_player_token(pin: str, player_id: int, token: str | None) -> None:
    payload = _jwt_decode(token)
    if payload.get("typ") != "player":
        raise HTTPException(status_code=401, detail="Невалидный токен игрока")

    signed_pin = payload.get("pin")
    signed_player_id = payload.get("pid")

    if signed_pin != pin.upper() or not isinstance(signed_player_id, int) or signed_player_id != player_id:
        raise HTTPException(status_code=403, detail="Токен игрока не подходит")
