"""Security helpers (JWT + password hashing).

Logic:
- Hash and verify passwords
- Create and decode JWT access tokens
"""

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(
    *,
    subject: str,
    role: str,
    user_id: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": exp}
    if user_id:
        # Keep both names for frontend/backward compatibility across teams.
        payload["user_id"] = user_id
        payload["student_id"] = user_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token.") from exc
