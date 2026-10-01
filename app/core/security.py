from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


class TokenValidationError(ValueError):
    pass


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, password_digest: str) -> bool:
    try:
        return password_hash.verify(password, password_digest)
    except Exception:
        return False


def create_token(
    *,
    user_id: int,
    token_type: str,
    expires_delta: timedelta,
) -> tuple[str, datetime]:
    issued_at = datetime.now(UTC)
    expires_at = issued_at + expires_delta
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": str(uuid4()),
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def create_access_token(user_id: int) -> tuple[str, datetime]:
    return create_token(
        user_id=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    return create_token(
        user_id=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, *, expected_type: str) -> dict[str, object]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "jti", "iat", "exp"]},
        )
    except InvalidTokenError as exc:
        raise TokenValidationError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise TokenValidationError("Unexpected token type")

    try:
        int(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("Invalid token subject") from exc

    return payload


def token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
