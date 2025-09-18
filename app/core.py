from __future__ import annotations
import logging
import os
from typing import Final
from telebot import TeleBot
from .guard import CallbackShield

# --- logging (простая настройка) ---
logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- конфиг ---
BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN env var is empty. Export BOT_TOKEN=<your token> and rerun."
    )

# --- единый бот на весь проект ---
bot: Final[TeleBot] = TeleBot(BOT_TOKEN, parse_mode="HTML")

shield: Final[CallbackShield] = CallbackShield(
    dedup_ttl=0.8,          # блокируем тот же колбэк ~800мс
    in_flight_timeout=2.0,  # сереализуем обработку колбэков на 2с
)