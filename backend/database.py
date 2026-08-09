import sqlite3
import os
import json
import uuid
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "actionlens.db"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it does not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Users table — includes email + OTP fields
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT NOT NULL,
        otp_code TEXT,
        otp_expires_at TEXT,
        otp_verified INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Migrate: add email/OTP columns to existing tables that lack them
    for col, col_def in [
        ("email", "TEXT NOT NULL DEFAULT ''"),
        ("otp_code", "TEXT"),
        ("otp_expires_at", "TEXT"),
        ("otp_verified", "INTEGER DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT,
        summary TEXT,
        extracted_json TEXT,
        raw_text TEXT,
        confidence_level TEXT,
        confidence_explanation TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        task_text TEXT,
        priority TEXT,
        days_to_complete INTEGER,
        dependencies TEXT,
        completed INTEGER DEFAULT 0,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
    """)

    # Chat Messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        role TEXT,
        content TEXT,
        evidence TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()

# ─── User + OTP Functions ─────────────────────────────────────

def get_or_create_user(username: str, email: str) -> dict:
    """
    Gets or creates a user by username+email pair.
    Returns dict with user info or raises ValueError on email mismatch.
    """
    username = username.strip().lower()
    email = email.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, username, email, otp_verified, created_at FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if user:
        # Existing user — verify email matches
        if user["email"] != email:
            conn.close()
            raise ValueError("EMAIL_MISMATCH")
        conn.close()
        return dict(user)

    # New user — create
    try:
        cursor.execute(
            "INSERT INTO users (username, email, otp_verified) VALUES (?, ?, 0)",
            (username, email)
        )
        conn.commit()
        cursor.execute("SELECT id, username, email, otp_verified, created_at FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
    except sqlite3.IntegrityError:
        pass

    conn.close()
    return dict(user) if user else None

def store_otp(user_id: int, otp: str, expires_at: str):
    """Saves the OTP and expiry for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET otp_code = ?, otp_expires_at = ?, otp_verified = 0 WHERE id = ?",
        (otp, expires_at, user_id)
    )
    conn.commit()
    conn.close()

def verify_otp(user_id: int, otp: str) -> bool:
    """
    Validates the OTP for a user.
    Returns True if valid and not expired, False otherwise.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT otp_code, otp_expires_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    stored_otp = row["otp_code"]
    expires_at_str = row["otp_expires_at"]

    if not stored_otp or not expires_at_str:
        conn.close()
        return False

    # Check expiry
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.utcnow() > expires_at:
            conn.close()
            return False
    except Exception:
        conn.close()
        return False

    # Check match
    if stored_otp != otp.strip():
        conn.close()
        return False

    # Mark as verified and clear OTP
    cursor.execute(
        "UPDATE users SET otp_verified = 1, otp_code = NULL, otp_expires_at = NULL WHERE id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    return True

# ─── Document Functions ───────────────────────────────────────

def save_document(user_id: int, doc_id: str, title: str, summary: str, extracted_json: dict,
                  raw_text: str, confidence_level: str, confidence_explanation: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO documents (id, user_id, title, summary, extracted_json, raw_text, confidence_level, confidence_explanation)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (doc_id, user_id, title, summary, json.dumps(extracted_json), raw_text, confidence_level, confidence_explanation))

    action_items = extracted_json.get("action_items", [])
    for idx, item in enumerate(action_items):
        task_id = f"{doc_id}_task_{idx}"
        deps = ",".join(item.get("dependencies", [])) if isinstance(item.get("dependencies"), list) else str(item.get("dependencies") or "")
        cursor.execute("""
        INSERT INTO tasks (id, document_id, task_text, priority, days_to_complete, dependencies, completed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (task_id, doc_id, item.get("task", ""), item.get("priority", "Medium"), item.get("days_to_complete", 0), deps))

    conn.commit()
    conn.close()

def get_user_documents(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, title, summary, confidence_level, confidence_explanation, created_at
    FROM documents WHERE user_id = ? ORDER BY created_at DESC
    """, (user_id,))
    docs = cursor.fetchall()

    result = []
    for doc in docs:
        d = dict(doc)
        cursor.execute("SELECT COUNT(*) as total, SUM(completed) as completed FROM tasks WHERE document_id = ?", (d["id"],))
        counts = cursor.fetchone()
        d["total_tasks"] = counts["total"] or 0
        d["completed_tasks"] = int(counts["completed"] or 0)
        result.append(d)

    conn.close()
    return result

def get_document_details(doc_id: str, user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, user_id, title, summary, extracted_json, raw_text, confidence_level, confidence_explanation, created_at
    FROM documents WHERE id = ? AND user_id = ?
    """, (doc_id, user_id))
    doc_row = cursor.fetchone()

    if not doc_row:
        conn.close()
        return None

    doc = dict(doc_row)
    doc["extracted_json"] = json.loads(doc["extracted_json"])

    cursor.execute("""
    SELECT id, task_text, priority, days_to_complete, dependencies, completed
    FROM tasks WHERE document_id = ?
    """, (doc_id,))
    tasks_rows = cursor.fetchall()

    doc["tasks"] = []
    for t in tasks_rows:
        td = dict(t)
        td["dependencies"] = [d.strip() for d in td["dependencies"].split(",") if d.strip()] if td["dependencies"] else []
        td["completed"] = bool(td["completed"])
        doc["tasks"].append(td)

    conn.close()
    return doc

def delete_document(doc_id: str, user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

# ─── Dashboard Aggregation ────────────────────────────────────

def get_user_dashboard(user_id: int) -> dict:
    """
    Returns ALL deadlines and pending tasks across all documents for a user,
    for the unified priority dashboard view.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # All documents for user
    cursor.execute("""
    SELECT id, title, extracted_json FROM documents WHERE user_id = ?
    """, (user_id,))
    docs = cursor.fetchall()

    all_deadlines = []
    all_pending_tasks = []

    for doc in docs:
        doc_id = doc["id"]
        doc_title = doc["title"]
        try:
            extracted = json.loads(doc["extracted_json"])
        except Exception:
            extracted = {}

        # Collect deadlines from extracted JSON
        for date_obj in extracted.get("dates", []):
            if date_obj.get("date"):
                all_deadlines.append({
                    "label": date_obj.get("label", "Deadline"),
                    "date": date_obj.get("date", ""),
                    "time": date_obj.get("time", None),
                    "explanation": date_obj.get("explanation", ""),
                    "doc_title": doc_title,
                    "doc_id": doc_id,
                })

        # Collect pending (incomplete) tasks
        cursor.execute("""
        SELECT id, task_text, priority, days_to_complete, dependencies, completed
        FROM tasks WHERE document_id = ? AND completed = 0
        """, (doc_id,))
        tasks = cursor.fetchall()
        for t in tasks:
            td = dict(t)
            td["doc_title"] = doc_title
            td["doc_id"] = doc_id
            td["dependencies"] = [d.strip() for d in td["dependencies"].split(",") if d.strip()] if td["dependencies"] else []
            all_pending_tasks.append(td)

    conn.close()

    # Sort deadlines by date ascending (soonest first)
    def parse_date_safe(d):
        try:
            return datetime.strptime(d["date"], "%Y-%m-%d")
        except Exception:
            return datetime(9999, 12, 31)

    all_deadlines.sort(key=parse_date_safe)

    # Sort pending tasks by priority: High=3, Medium=2, Low=1
    priority_order = {"High": 3, "Medium": 2, "Low": 1}
    all_pending_tasks.sort(key=lambda t: priority_order.get(t.get("priority", "Low"), 1), reverse=True)

    return {
        "deadlines": all_deadlines,
        "pending_tasks": all_pending_tasks,
    }

# ─── Task Functions ───────────────────────────────────────────

def toggle_task_completion(task_id: str, completed: bool, user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.id FROM tasks t
    JOIN documents d ON t.document_id = d.id
    WHERE t.id = ? AND d.user_id = ?
    """, (task_id, user_id))

    if not cursor.fetchone():
        conn.close()
        return False

    cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?", (1 if completed else 0, task_id))
    conn.commit()
    conn.close()
    return True

# ─── Chat Functions ───────────────────────────────────────────

def save_chat_message(doc_id: str, role: str, content: str, evidence: str = None) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute("""
    INSERT INTO chat_messages (id, document_id, role, content, evidence, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (msg_id, doc_id, role, content, evidence, now))
    conn.commit()
    conn.close()

    return {"id": msg_id, "document_id": doc_id, "role": role, "content": content, "evidence": evidence, "created_at": now}

def get_chat_history(doc_id: str, limit: int = 50):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, role, content, evidence, created_at
    FROM chat_messages WHERE document_id = ?
    ORDER BY created_at ASC LIMIT ?
    """, (doc_id, limit))
    msgs = cursor.fetchall()
    conn.close()
    return [dict(m) for m in msgs]
