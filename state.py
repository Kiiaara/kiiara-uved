"""Хранение состояния стрима в JSON-файле рядом со скриптом."""
import json
import os
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state.json"

# Дефолтное состояние - канал оффлайн, ничего не знаем
DEFAULT_STATE = {
    "is_live": False,
    "stream_id": None,
    "offline_misses": 0,  # счётчик подряд оффлайн-тиков для защиты от флапа
    "sent_messages": [],  # [{chat_id, message_id}] постов о старте - удаляем при завершении
}


def load_state() -> dict:
    """Читает state.json. Если нет или битый - возвращает дефолт."""
    if not STATE_FILE.exists():
        return dict(DEFAULT_STATE)
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Дополняем недостающие ключи на случай, если схему расширим
        merged = dict(DEFAULT_STATE)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_STATE)


def save_state(data: dict) -> None:
    """Атомарная запись через временный файл + os.replace."""
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)
