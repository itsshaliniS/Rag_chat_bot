import json
import os
import re
from functools import wraps

from flask import session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

import config

USERS_FILE = os.path.join(config.BASE_DIR, "users.json")

# email check pattern
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DEFAULT_USERS = {
    "admin": {
        "password_hash": generate_password_hash("admin123"),
        "name": "Admin",
        "email": "admin@example.com",
    },
    "shalini": {
        "password_hash": generate_password_hash("shalini123"),
        "name": "Shalini",
        "email": "shalini@example.com",
    },
}


def _load_users():
    if not os.path.exists(USERS_FILE):
        _save_users(DEFAULT_USERS)
        return dict(DEFAULT_USERS)

    with open(USERS_FILE, 'r') as f:
        return json.load(f)


def _save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)


def verify_login(username, password):
    users = _load_users()
    record = users.get(username)
    if not record:
        return False
    return check_password_hash(record["password_hash"], password)


def create_user(username, password, name="", email=""):
    username = username.strip()
    name = name.strip()
    email = email.strip()

    if not username or not password or not name or not email:
        return False, "All fields are required."

    if len(password) < 4:
        return False, "Password must be at least 4 characters."

    if not EMAIL_PATTERN.match(email):
        return False, "Please enter a valid email address."

    users = _load_users()

    if username in users:
        return False, "That username is already taken."

    users[username] = {
        "password_hash": generate_password_hash(password),
        "name": name,
        "email": email,
    }
    _save_users(users)
    return True, ""


def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if not session.get("username"):
            return jsonify({"error": "Please log in to upload documents."}), 401
        return route_function(*args, **kwargs)
    return wrapper