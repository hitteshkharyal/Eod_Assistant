"""Password hashing and authenticated account records."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass

from ai_eod_assistant.database.models import utc_now


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    role: str
    team_id: int
    team_name: str


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 240_000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def initialize_auth(connection: sqlite3.Connection) -> None:
    """Create the initial alpha team and admin without overwriting accounts."""
    team = connection.execute("SELECT id FROM teams WHERE name = 'alpha'").fetchone()
    if team is None:
        connection.execute("INSERT INTO teams (name, created_at) VALUES (?, ?)", ("alpha", utc_now().isoformat()))
        team = connection.execute("SELECT id FROM teams WHERE name = 'alpha'").fetchone()
    admin = connection.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if admin is None:
        connection.execute(
            "INSERT INTO users (team_id, username, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
            (int(team["id"]), "admin", hash_password("admin123"), utc_now().isoformat()),
        )
    connection.commit()


def authenticate(connection: sqlite3.Connection, username: str, password: str) -> AuthUser | None:
    row = connection.execute(
        "SELECT users.id, users.username, users.password_hash, users.role, users.team_id, teams.name AS team_name "
        "FROM users JOIN teams ON teams.id = users.team_id WHERE users.username = ? AND users.is_active = 1",
        (username.strip(),),
    ).fetchone()
    if row is None or not verify_password(password, str(row["password_hash"])):
        return None
    return AuthUser(int(row["id"]), str(row["username"]), str(row["role"]), int(row["team_id"]), str(row["team_name"]))


def create_team_admin(connection: sqlite3.Connection, username: str, password: str, team_name: str) -> AuthUser:
    cleaned_username, cleaned_team = username.strip(), team_name.strip()
    if not cleaned_username or not password or not cleaned_team:
        raise ValueError("Username, password, and team name are required.")
    connection.execute("INSERT INTO teams (name, created_at) VALUES (?, ?)", (cleaned_team, utc_now().isoformat()))
    team = connection.execute("SELECT id FROM teams WHERE name = ?", (cleaned_team,)).fetchone()
    connection.execute(
        "INSERT INTO users (team_id, username, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
        (int(team["id"]), cleaned_username, hash_password(password), utc_now().isoformat()),
    )
    connection.commit()
    return authenticate(connection, cleaned_username, password)  # type: ignore[return-value]


def create_member(connection: sqlite3.Connection, username: str, password: str, team_id: int) -> AuthUser:
    cleaned_username = username.strip()
    if not cleaned_username or not password:
        raise ValueError("Username and password are required.")
    connection.execute(
        "INSERT INTO users (team_id, username, password_hash, role, created_at) VALUES (?, ?, ?, 'member', ?)",
        (team_id, cleaned_username, hash_password(password), utc_now().isoformat()),
    )
    connection.commit()
    return authenticate(connection, cleaned_username, password)  # type: ignore[return-value]


def team_members(connection: sqlite3.Connection, team_id: int) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT id, username, role, created_at FROM users WHERE team_id = ? ORDER BY role DESC, username ASC", (team_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def change_password(connection: sqlite3.Connection, requester: AuthUser, target_username: str, new_password: str) -> None:
    """Change a password while enforcing team-leader ownership boundaries."""
    if not new_password:
        raise ValueError("A new password is required.")
    target = connection.execute("SELECT id, team_id FROM users WHERE username = ? AND is_active = 1", (target_username.strip(),)).fetchone()
    if target is None or (requester.username != "admin" and int(target["team_id"]) != requester.team_id):
        raise PermissionError("You can change passwords only for users in your team.")
    connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), int(target["id"])))
    connection.commit()


def recover_root_admin(connection: sqlite3.Connection, recovery_key: str, new_password: str, expected_key: str | None) -> None:
    """Recover the seeded root admin using a local environment recovery key."""
    if not expected_key or not hmac.compare_digest(recovery_key, expected_key):
        raise PermissionError("Invalid admin recovery key.")
    if not new_password:
        raise ValueError("A new password is required.")
    connection.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (hash_password(new_password),))
    connection.commit()