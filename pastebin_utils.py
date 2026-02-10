"""Pastebin API integration — settings, login, CRUD paste."""

from __future__ import annotations

import json
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any

import requests

import database as db

log: logging.Logger = logging.getLogger("pastebin")

SETTINGS_PATH: str = os.path.join(db.DATA_DIR, "pastebin_settings.json")

API_BASE: str = "https://pastebin.com/api"
API_POST: str = f"{API_BASE}/api_post.php"
API_LOGIN: str = f"{API_BASE}/api_login.php"
API_RAW: str = f"{API_BASE}/api_raw.php"

VISIBILITY_LABELS: dict[int, str] = {
    0: "Pubblico",
    1: "Unlisted",
    2: "Privato",
}

EXPIRE_OPTIONS: dict[str, str] = {
    "N": "Mai",
    "10M": "10 minuti",
    "1H": "1 ora",
    "1D": "1 giorno",
    "1W": "1 settimana",
    "2W": "2 settimane",
    "1M": "1 mese",
    "6M": "6 mesi",
    "1Y": "1 anno",
}


def get_settings() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "api_dev_key": "",
        "api_user_key": "",
        "username": "",
        "default_visibility": 1,
        "default_expire": "N",
    }
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH) as f:
                saved = json.load(f)
                defaults.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_settings(settings: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    db._secure_file(SETTINGS_PATH)


def is_configured() -> bool:
    return bool(get_settings().get("api_dev_key"))


def has_user_key() -> bool:
    return bool(get_settings().get("api_user_key"))


def login(api_dev_key: str, username: str, password: str) -> tuple[bool, str]:
    """Login to Pastebin and return (success, api_user_key_or_error)."""
    try:
        resp = requests.post(
            API_LOGIN,
            data={
                "api_dev_key": api_dev_key,
                "api_user_name": username,
                "api_user_password": password,
            },
            timeout=15,
        )
        text = resp.text.strip()
        if resp.status_code == 200 and not text.startswith("Bad API request"):
            return True, text
        return False, text
    except requests.RequestException as e:
        raise ConnectionError(f"Errore connessione Pastebin: {e}") from e


def create_paste(
    content: str,
    title: str = "",
    visibility: int = 1,
    expire_date: str = "N",
) -> tuple[bool, str]:
    """Create a paste. Returns (success, url_or_error)."""
    settings = get_settings()
    api_dev_key = settings.get("api_dev_key", "")
    if not api_dev_key:
        return False, "API key non configurata"

    data: dict[str, str] = {
        "api_dev_key": api_dev_key,
        "api_option": "paste",
        "api_paste_code": content,
        "api_paste_name": title,
        "api_paste_private": str(visibility),
        "api_paste_expire_date": expire_date,
    }

    api_user_key = settings.get("api_user_key", "")
    if api_user_key:
        data["api_user_key"] = api_user_key

    try:
        resp = requests.post(API_POST, data=data, timeout=30)
        text = resp.text.strip()
        if resp.status_code == 200 and text.startswith("https://"):
            return True, text
        return False, text
    except requests.RequestException as e:
        raise ConnectionError(f"Errore connessione Pastebin: {e}") from e


def list_user_pastes(limit: int = 50) -> tuple[bool, list[dict[str, str]] | str]:
    """List user's pastes. Returns (success, list_or_error)."""
    settings = get_settings()
    api_dev_key = settings.get("api_dev_key", "")
    api_user_key = settings.get("api_user_key", "")
    if not api_dev_key or not api_user_key:
        return False, "API key o login non configurati"

    try:
        resp = requests.post(
            API_POST,
            data={
                "api_dev_key": api_dev_key,
                "api_user_key": api_user_key,
                "api_option": "list",
                "api_results_limit": str(limit),
            },
            timeout=15,
        )
        text = resp.text.strip()
        if resp.status_code == 200 and not text.startswith("Bad API request"):
            if text == "No pastes found.":
                return True, []
            return True, _parse_paste_list(text)
        return False, text
    except requests.RequestException as e:
        raise ConnectionError(f"Errore connessione Pastebin: {e}") from e


def delete_paste(paste_key: str) -> tuple[bool, str]:
    """Delete a paste from Pastebin. Returns (success, message)."""
    settings = get_settings()
    api_dev_key = settings.get("api_dev_key", "")
    api_user_key = settings.get("api_user_key", "")
    if not api_dev_key or not api_user_key:
        return False, "API key o login non configurati"

    try:
        resp = requests.post(
            API_POST,
            data={
                "api_dev_key": api_dev_key,
                "api_user_key": api_user_key,
                "api_option": "delete",
                "api_paste_key": paste_key,
            },
            timeout=15,
        )
        text = resp.text.strip()
        if resp.status_code == 200 and "removed" in text.lower():
            return True, text
        return False, text
    except requests.RequestException as e:
        raise ConnectionError(f"Errore connessione Pastebin: {e}") from e


def extract_paste_key(url: str) -> str:
    """Extract paste key from a Pastebin URL."""
    return url.rstrip("/").rsplit("/", 1)[-1]


def _parse_paste_list(xml_text: str) -> list[dict[str, str]]:
    """Parse Pastebin XML paste list (no root element)."""
    wrapped = f"<root>{xml_text}</root>"
    root = ET.fromstring(wrapped)  # noqa: S314
    pastes: list[dict[str, str]] = []
    for paste_el in root.findall("paste"):
        item: dict[str, str] = {}
        for child in paste_el:
            item[child.tag] = child.text or ""
        pastes.append(item)
    return pastes
