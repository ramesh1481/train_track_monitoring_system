import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, "database.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'inspector'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image TEXT,
        output TEXT,
        severity TEXT,
        status TEXT,
        created_at TEXT,
        completed_at TEXT,
        completed_by TEXT,
        location TEXT,
        description TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER,
        channel TEXT,
        recipient TEXT,
        message TEXT,
        sent_at TEXT
    )
    """)

    # Lightweight migration for older databases.
    c.execute("PRAGMA table_info(complaints)")
    complaint_columns = [row[1] for row in c.fetchall()]
    if "completed_by" not in complaint_columns:
        c.execute("ALTER TABLE complaints ADD COLUMN completed_by TEXT")
    if "location" not in complaint_columns:
        c.execute("ALTER TABLE complaints ADD COLUMN location TEXT")
    if "description" not in complaint_columns:
        c.execute("ALTER TABLE complaints ADD COLUMN description TEXT")

    c.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in c.fetchall()]
    if "role" not in user_columns:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'inspector'")

    c.execute("SELECT id, password FROM users WHERE username=?", ("admin",))
    admin = c.fetchone()
    if not admin:
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin"),
        )
    else:
        user_id, password = admin
        # Keep compatibility with old plaintext records and harden at startup.
        if not password.startswith("scrypt:"):
            c.execute(
                "UPDATE users SET password=? WHERE id=?",
                (generate_password_hash("admin123"), user_id),
            )
        c.execute("UPDATE users SET role='admin' WHERE username='admin'")

    # Additional default users.
    defaults = [
        ("inspector", "inspect123", "inspector"),
        ("supervisor", "super123", "supervisor"),
    ]
    for username, pwd, role in defaults:
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(pwd), role),
            )

    conn.commit()
    conn.close()