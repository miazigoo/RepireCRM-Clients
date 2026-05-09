import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as _jwt  # PyJWT

from .config import Settings


class AuthError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        raise ValueError("Укажите корректный email")
    return value


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Укажите корректный номер телефона")
    return f"+{digits}"


def normalize_identity(identity_type: str, value: str) -> str:
    if identity_type == "email":
        return normalize_email(value)
    if identity_type == "phone":
        return normalize_phone(value)
    raise ValueError("Некорректный тип контакта")


def detect_identity_type(value: str) -> str:
    return "email" if "@" in value else "phone"


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Пароль должен быть не короче 8 символов")
    if password.isdigit() or password.isalpha():
        raise ValueError("Пароль должен содержать разные типы символов")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180_000)
    return f"pbkdf2_sha256$180000${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), code.encode(), hashlib.sha256).hexdigest()


def verify_code(code: str, code_hash: str, secret_key: str) -> bool:
    return hmac.compare_digest(hash_code(code.strip(), secret_key), code_hash)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# Access tokens (PyJWT HS256)
# ──────────────────────────────────────────────────────────────────────────────


def create_access_token(customer_id: int, settings: Settings) -> str:
    """Issue a signed JWT access token (HS256)."""
    now = utcnow()
    payload = {
        "sub": str(customer_id),
        "scope": "customer",
        "iat": now,
        "exp": now + timedelta(minutes=settings.token_ttl_minutes),
    }
    return _jwt.encode(payload, settings.secret_key, algorithm="HS256")


def parse_access_token(token: str, settings: Settings) -> int:
    """Verify and decode a JWT access token; return customer_id.

    Falls back to the legacy ``{b64payload}.{hmac_hex}`` format for tokens
    issued before the PyJWT migration so existing sessions aren't invalidated.
    """
    try:
        payload: dict[str, Any] = _jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "scope"]},
        )
    except _jwt.ExpiredSignatureError as exc:
        raise AuthError("Сессия истекла") from exc
    except _jwt.PyJWTError:
        # Try legacy pre-migration format
        return _parse_legacy_token(token, settings)

    if payload.get("scope") != "customer":
        raise AuthError("Некорректный токен")
    return int(payload["sub"])


# ──────────────────────────────────────────────────────────────────────────────
# Legacy token helpers (kept for backward-compat during migration window)
# ──────────────────────────────────────────────────────────────────────────────


def _parse_legacy_token(token: str, settings: Settings) -> int:
    """Parse the old custom ``{b64payload}.{hmac_hex}`` format."""
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("Некорректный токен") from exc

    if not hmac.compare_digest(_sign(body, settings.secret_key), signature):
        raise AuthError("Некорректная подпись токена")

    try:
        raw: dict[str, Any] = json.loads(_unb64(body))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AuthError("Некорректный токен") from exc

    if raw.get("scope") != "customer":
        raise AuthError("Некорректный токен")
    if int(raw.get("exp", 0)) < int(utcnow().timestamp()):
        raise AuthError("Сессия истекла")
    return int(raw["sub"])


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(value: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()
