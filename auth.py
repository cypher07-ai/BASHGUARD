"""
BashGuard — Auth System
========================
Login/Register system using SQLite.
- First run: user registers (sets username + password)
- After that: only that username+password can login
- Passwords are hashed with SHA-256 + salt (never stored plain)
- Returns a session token on login (frontend stores this)
- Token required for protected endpoints

Endpoints:
  POST /auth/register  — first-time setup only
  POST /auth/login     — login, get token
  POST /auth/logout    — invalidate token
  GET  /auth/status    — is anyone registered? is token valid?
  GET  /auth/me        — get current user info (needs token)
"""

import os
import sys
import sqlite3
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from dataclasses import dataclass

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Database path ──
DB_PATH = os.path.join(os.path.dirname(__file__), "bashguard_auth.db")

# ── Session expiry (hours) ──
SESSION_HOURS = 24


# ============================================================
#  DATABASE SETUP
# ============================================================

def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt        TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            token       TEXT UNIQUE NOT NULL,
            username    TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1
        );
    """)
    conn.commit()
    conn.close()


# Run on import
init_db()


# ============================================================
#  PASSWORD HASHING
# ============================================================

def _generate_salt(length: int = 32) -> str:
    """Generate a random salt."""
    return secrets.token_hex(length)


def _hash_password(password: str, salt: str) -> str:
    """Hash password with salt using SHA-256."""
    salted = (salt + password + salt).encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def _verify_password(password: str, salt: str, stored_hash: str) -> bool:
    """Check if password matches stored hash."""
    return _hash_password(password, salt) == stored_hash


# ============================================================
#  SESSION TOKENS
# ============================================================

def _generate_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(48)


def _is_token_valid(token: str) -> bool:
    """Check if token exists, is active, and not expired."""
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM sessions
        WHERE token = ? AND is_active = 1
    """, (token,)).fetchone()
    conn.close()

    if not row:
        return False

    # Check expiry
    expires = datetime.fromisoformat(row["expires_at"])
    return datetime.utcnow() < expires


def _get_username_from_token(token: str) -> str:
    """Get username from a valid token."""
    conn = get_db()
    row = conn.execute("""
        SELECT username FROM sessions
        WHERE token = ? AND is_active = 1
    """, (token,)).fetchone()
    conn.close()

    if not row:
        return ""

    return row["username"]


# ============================================================
#  CORE AUTH FUNCTIONS
# ============================================================

def is_anyone_registered() -> bool:
    """Returns True if at least one user is registered."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count > 0


def register_user(username: str, password: str) -> dict:
    """
    Register a new user. Only works if NO user is registered yet.
    This is a one-time setup — BashGuard supports one user.
    """
    if not username or not username.strip():
        return {"success": False, "error": "Username cannot be empty"}

    if not password or len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters"}

    if is_anyone_registered():
        return {
            "success": False,
            "error": "A user is already registered. Use /auth/login instead."
        }

    username = username.strip().lower()

    # Check username has no weird chars
    allowed = set(string.ascii_lowercase + string.digits + "_-.")
    if not all(c in allowed for c in username):
        return {"success": False, "error": "Username can only contain letters, numbers, _ - ."}

    salt = _generate_salt()
    password_hash = _hash_password(password, salt)

    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO users (username, password_hash, salt, created_at)
            VALUES (?, ?, ?, ?)
        """, (username, password_hash, salt, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"User '{username}' registered successfully. You can now login.",
            "username": username,
        }
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Username already exists"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def login_user(username: str, password: str) -> dict:
    """Login with username + password. Returns session token on success."""
    if not username or not password:
        return {"success": False, "error": "Username and password required"}

    username = username.strip().lower()

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if not row:
        return {"success": False, "error": "Invalid username or password"}

    if not _verify_password(password, row["salt"], row["password_hash"]):
        return {"success": False, "error": "Invalid username or password"}

    # Create session token
    token = _generate_token()
    now = datetime.utcnow()
    expires = now + timedelta(hours=SESSION_HOURS)

    conn = get_db()
    conn.execute("""
        INSERT INTO sessions (token, username, created_at, expires_at, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (token, username, now.isoformat(), expires.isoformat()))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": f"Welcome back, {username}!",
        "token": token,
        "username": username,
        "expires_at": expires.isoformat(),
        "expires_in_hours": SESSION_HOURS,
    }


def logout_user(token: str) -> dict:
    """Invalidate a session token."""
    conn = get_db()
    conn.execute(
        "UPDATE sessions SET is_active = 0 WHERE token = ?", (token,)
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "Logged out successfully"}


def get_auth_status() -> dict:
    """Returns the current auth setup status."""
    registered = is_anyone_registered()
    conn = get_db()

    user = None
    if registered:
        row = conn.execute("SELECT username, created_at FROM users LIMIT 1").fetchone()
        if row:
            user = {"username": row["username"], "registered_at": row["created_at"]}

    active_sessions = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE is_active = 1"
    ).fetchone()[0]

    conn.close()

    return {
        "is_registered": registered,
        "setup_required": not registered,
        "user": user,
        "active_sessions": active_sessions,
        "message": (
            "No user registered yet. POST /auth/register to set up."
            if not registered
            else f"User registered. POST /auth/login to continue."
        ),
    }


def validate_token(token: str) -> dict:
    """Validate a token and return user info."""
    if not token:
        return {"valid": False, "error": "No token provided"}

    if not _is_token_valid(token):
        return {"valid": False, "error": "Token is invalid or expired"}

    username = _get_username_from_token(token)
    return {
        "valid": True,
        "username": username,
        "message": "Token is valid",
    }


def change_password(token: str, old_password: str, new_password: str) -> dict:
    """Change password for authenticated user."""
    if not _is_token_valid(token):
        return {"success": False, "error": "Not authenticated"}

    if len(new_password) < 6:
        return {"success": False, "error": "New password must be at least 6 characters"}

    username = _get_username_from_token(token)

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not _verify_password(old_password, row["salt"], row["password_hash"]):
        conn.close()
        return {"success": False, "error": "Current password is incorrect"}

    new_salt = _generate_salt()
    new_hash = _hash_password(new_password, new_salt)

    conn.execute("""
        UPDATE users SET password_hash = ?, salt = ? WHERE username = ?
    """, (new_hash, new_salt, username))
    conn.commit()

    # Invalidate all other sessions
    conn.execute(
        "UPDATE sessions SET is_active = 0 WHERE username = ? AND token != ?",
        (username, token)
    )
    conn.commit()
    conn.close()

    return {"success": True, "message": "Password changed successfully"}


# ============================================================
#  MIDDLEWARE HELPER — for protecting endpoints
# ============================================================

def require_auth(token: str) -> tuple:
    """
    Use in FastAPI endpoints to require authentication.
    Returns (is_valid: bool, username: str, error: str)
    """
    if not token:
        return False, "", "Authentication required. Include token in Authorization header."

    if not _is_token_valid(token):
        return False, "", "Invalid or expired token. Please login again."

    username = _get_username_from_token(token)
    return True, username, ""
