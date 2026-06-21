import sqlite3
import bcrypt
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "cabinet_clear.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Users tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    # Persistent scan and medical extraction logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            diagnosis TEXT,
            letter_payload TEXT,
            cabinet_payload TEXT,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def register_user(username: str, password: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", 
                       (username.lower().strip(), hash_password(password), datetime.now().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(username: str, password: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = ?",
                   (username.lower().strip(),))
    result = cursor.fetchone()
    conn.close()
    if result is None:
        return False
    return bcrypt.checkpw(password.encode(), result[0].encode())

def save_history_record(username: str, diagnosis: str, letter: dict, cabinet: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO history (username, timestamp, diagnosis, letter_payload, cabinet_payload)
        VALUES (?, ?, ?, ?, ?)
    ''', (username.lower().strip(), datetime.now().isoformat(), diagnosis, json.dumps(letter), json.dumps(cabinet)))
    conn.commit()
    conn.close()

def fetch_user_history(username: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, diagnosis, letter_payload, cabinet_payload FROM history WHERE username = ? ORDER BY timestamp DESC", 
                   (username.lower().strip(),))
    rows = cursor.fetchall()
    conn.close()
    return [{
        "timestamp": r[0],
        "diagnosis": r[1],
        "letter_data": json.loads(r[2]),
        "cabinet_data": json.loads(r[3])
    } for r in rows]

# Ensure DB infrastructure maps out instantly
init_db()
