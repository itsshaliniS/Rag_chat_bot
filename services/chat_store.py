import json
import os
import uuid
from datetime import datetime

import config

STORE_FILE = os.path.join(config.BASE_DIR, "chat_sessions.json")


def _load():
    if not os.path.exists(STORE_FILE):
        return {}
    with open(STORE_FILE, "r") as f:
        return json.load(f)


def _save(data):
    with open(STORE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def create_session(owner_id):
    data = _load()
    data.setdefault(owner_id, {})

    session_id = str(uuid.uuid4())
    data[owner_id][session_id] = {
        "title": None,
        "created_at": datetime.now().isoformat(),
        "messages": [],
    }
    _save(data)
    return session_id


def get_session(owner_id, session_id):
    data = _load()
    record = data.get(owner_id, {}).get(session_id)
    return record["messages"] if record else None


def list_sessions(owner_id):
    data = _load()
    owner_sessions = data.get(owner_id, {})

    sessions = [
        {
            "id": session_id,
            "title": record["title"] or "New chat",
            "created_at": record["created_at"],
        }
        for session_id, record in owner_sessions.items()
    ]
    sessions.sort(key=lambda s: s["created_at"], reverse=True)
    return sessions


def append_message(owner_id, session_id, role, text, timestamp, sources=None):
    data = _load()
    record = data.get(owner_id, {}).get(session_id)
    if not record:
        return

    record["messages"].append({
        "role": role,
        "text": text,
        "timestamp": timestamp,
        "sources": sources or [],
    })

    if record["title"] is None and role == "user":
        record["title"] = text[:40] + ("..." if len(text) > 40 else "")

    _save(data)