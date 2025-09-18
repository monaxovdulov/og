from __future__ import annotations
from .core import bot, logger

# ВАЖНО: импортируем, чтобы зарегистрировать handlers через декораторы
from . import commands  # noqa: F401
from . import callbacks # noqa: F401

def main() -> None:
    logger.info("Starting polling…")
    # infinity_polling удобен для демо; в проде — webhook
    bot.infinity_polling(skip_pending=True, timeout=30)

if __name__ == "__main__":
    main()
