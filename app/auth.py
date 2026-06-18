"""Authentication: password hashing, the bootstrap admin user, and a
session-based login guard for FastAPI routes.

Sessions are signed cookies (Starlette SessionMiddleware). Because the panel is
intended to be reached through an SSH tunnel and bound to localhost, this stays
deliberately simple.
"""
import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User


def hash_password(password: str) -> str:
    # bcrypt operates on the first 72 bytes; truncate explicitly to avoid errors.
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    pw = password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def ensure_admin(db: Session) -> None:
    """Create the admin user on first run from env settings."""
    existing = db.scalar(select(User).where(User.username == settings.admin_username))
    if existing:
        return
    pw_hash = settings.admin_password_hash or hash_password(settings.admin_password)
    db.add(User(username=settings.admin_username, password_hash=pw_hash))
    db.commit()


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user and verify_password(password, user.password_hash):
        return user
    return None


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency that enforces an authenticated session."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"Location": "/login"},
        )
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
