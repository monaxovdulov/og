from __future__ import annotations
from .core import bot
from .keyboards import kb_main_menu

@bot.message_handler(commands=["start", "menu"])
def cmd_start(message) -> None:
    """
    /start — приветствие + главное меню.
    """
    bot.send_message(
        message.chat.id,
        "<b>Привет!</b> Это демо-квиз-бот.\nВыберите действие:",
        reply_markup=kb_main_menu(),
    )
