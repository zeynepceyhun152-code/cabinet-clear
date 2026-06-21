import sqlite3
import hashlib
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "cabinet_clear.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            diagnosis TEXT,
            scan_payload TEXT,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

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

def get_user_history(username: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, diagnosis, scan_payload FROM scan_history WHERE username = ? ORDER BY timestamp DESC",
                   (username.lower().strip(),))
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("=== CABINET CLEAR LOG PANEL ===")
    print("1. Register Account\n2. View User Diagnostic Logs")
    choice = input("Select choice: ")
    if choice == "1":
        u = input("Username: ")
        p = input("Password: ")
        if register_user(u, p): print(f"✅ User {u} configured.")
        else: print("❌ Username already registered.")
    elif choice == "2":
        u = input("Target username: ")
        logs = get_user_history(u)
        if not logs: print("No log details found.")
        for l in logs:
            print(f"\nTime: {l[0]}\nContext: {l[1]}\nPayload Data: {l[2]}")
