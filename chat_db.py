import json
import uuid
import os
from datetime import datetime

# Directory to store chat history JSON files
HISTORY_DIR = os.path.join(os.path.dirname(__file__), "chat_history")
INDEX_FILE = os.path.join(HISTORY_DIR, "_index.json")


def _ensure_dir():
    """Creates the chat_history directory if it doesn't exist."""
    os.makedirs(HISTORY_DIR, exist_ok=True)


def _load_index() -> list:
    """Loads the session index (list of session metadata)."""
    _ensure_dir()
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_index(index: list):
    """Saves the session index."""
    _ensure_dir()
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def _session_file(session_id: str) -> str:
    """Returns the file path for a session's messages."""
    return os.path.join(HISTORY_DIR, f"{session_id}.json")


def create_session(first_message: str) -> str:
    """
    Creates a new session with an auto-generated title from the first message.

    Args:
        first_message: The user's first message, used to generate the title.

    Returns:
        The new session's UUID string.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    # Auto-generate title: first 50 chars of the message
    title = first_message.strip()
    if len(title) > 50:
        title = title[:47] + "..."
    if not title:
        title = "New Conversation"

    # Add to index
    index = _load_index()
    index.insert(0, {
        "id": session_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    })
    _save_index(index)

    # Create empty messages file
    with open(_session_file(session_id), "w", encoding="utf-8") as f:
        json.dump([], f)

    return session_id


def save_message(session_id: str, role: str, content: str):
    """
    Saves a message to a session and updates the session's updated_at timestamp.

    Args:
        session_id: The session UUID to save the message to.
        role: 'user' or 'assistant'.
        content: The message text.
    """
    now = datetime.now().isoformat()
    filepath = _session_file(session_id)

    # Load existing messages
    messages = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except (json.JSONDecodeError, IOError):
            messages = []

    # Append new message
    messages.append({
        "role": role,
        "content": content,
        "timestamp": now,
    })

    # Save messages
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)

    # Update timestamp in index
    index = _load_index()
    for session in index:
        if session["id"] == session_id:
            session["updated_at"] = now
            break
    # Re-sort by updated_at descending
    index.sort(key=lambda s: s["updated_at"], reverse=True)
    _save_index(index)


def get_session_list(limit: int = 50) -> list:
    """
    Returns a lightweight list of past sessions for the sidebar.

    Args:
        limit: Max number of sessions to return.

    Returns:
        List of dicts with keys: id, title, created_at, updated_at.
    """
    index = _load_index()
    return index[:limit]


def load_session(session_id: str) -> list:
    """
    Loads the full message history for a session.

    Args:
        session_id: The session UUID.

    Returns:
        List of dicts with keys: role, content, timestamp — ordered chronologically.
    """
    filepath = _session_file(session_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def delete_session(session_id: str):
    """
    Deletes a session and its messages file.

    Args:
        session_id: The session UUID to delete.
    """
    # Remove from index
    index = _load_index()
    index = [s for s in index if s["id"] != session_id]
    _save_index(index)

    # Delete messages file
    filepath = _session_file(session_id)
    if os.path.exists(filepath):
        os.remove(filepath)


def get_session_title(session_id: str) -> str:
    """
    Gets the title of a specific session.

    Args:
        session_id: The session UUID.

    Returns:
        The session title string, or 'Conversation' if not found.
    """
    index = _load_index()
    for session in index:
        if session["id"] == session_id:
            return session["title"]
    return "Conversation"
