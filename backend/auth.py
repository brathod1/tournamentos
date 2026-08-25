"""Authentication for TournamentOS.

Model (per product decision):
  * Organizers hold individual accounts (email + password); all of them share the same data.
  * Everything that CHANGES data requires a valid token.
  * Reading fixtures/schedule/standings is public so players and parents can follow along —
    but personal contact details are stripped for anonymous callers.

Deliberately small: bcrypt password hashing + stateless JWTs, no third-party identity provider.
"""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

JWT_ALGO = "HS256"
TOKEN_TTL_HOURS = int(os.environ.get("TOKEN_TTL_HOURS", "12"))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LEN = 8
BCRYPT_MAX_BYTES = 72          # bcrypt silently truncates beyond this — reject instead
PII_FIELDS = ("phone", "contact")   # hidden from anonymous readers


def jwt_secret() -> str:
    """Signing key. MUST be set in production; dev falls back to a fixed local-only key."""
    s = os.environ.get("JWT_SECRET")
    if s:
        return s
    if os.environ.get("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError("JWT_SECRET must be set when ENVIRONMENT=production")
    return "dev-only-insecure-secret-change-me"


# --------------------------------------------------------------------- models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    role: str = "organizer"          # "admin" can manage other users
    password_hash: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str
    role: str = "organizer"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def public_user(u: dict) -> dict:
    """User document without the password hash."""
    return {k: v for k, v in u.items() if k not in ("password_hash", "_id")}


# ------------------------------------------------------------------ passwords
def hash_password(pw: str) -> str:
    validate_password(pw)
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password(pw: str):
    if not pw or len(pw) < MIN_PASSWORD_LEN:
        raise HTTPException(422, f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    if len(pw.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise HTTPException(422, "Password is too long (max 72 bytes).")


def normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL_RE.match(e):
        raise HTTPException(422, "Enter a valid email address.")
    return e


# --------------------------------------------------------------------- tokens
def create_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "organizer"),
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, jwt_secret(), algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired — please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid session — please sign in again.")


# ---------------------------------------------------------------- dependencies
bearer = HTTPBearer(auto_error=False)


def make_auth_deps(db):
    """Build the FastAPI dependencies, bound to the app's database handle."""

    async def current_user_optional(
        creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    ) -> Optional[dict]:
        if not creds:
            return None
        payload = decode_token(creds.credentials)
        user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
        if not user:
            raise HTTPException(401, "Account no longer exists.")
        return user

    async def require_user(user: Optional[dict] = Depends(current_user_optional)) -> dict:
        if not user:
            raise HTTPException(401, "Sign in to make changes.")
        return user

    async def require_admin(user: dict = Depends(require_user)) -> dict:
        if user.get("role") != "admin":
            raise HTTPException(403, "Only an admin can manage user accounts.")
        return user

    return current_user_optional, require_user, require_admin


def strip_pii(doc, keep: bool):
    """Remove personal contact details for anonymous readers.
    Accepts a dict or a list of dicts; returns the same shape."""
    if keep:
        return doc
    if isinstance(doc, list):
        return [strip_pii(d, keep) for d in doc]
    if isinstance(doc, dict):
        return {k: v for k, v in doc.items() if k not in PII_FIELDS}
    return doc
