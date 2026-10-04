import os
import hashlib
import hmac
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from app.core.config import settings

def get_password_hash(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2_sha256$100000${salt.hex()}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against PBKDF2-HMAC-SHA256 hash."""
    try:
        algorithm, iterations_str, salt_hex, key_hex = hashed_password.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Generate RFC 7519 standard HS256 JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[str]:
    """Decode and validate standard JWT token, returning user id subject."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except (jwt.PyJWTError, ValueError):
        return None
