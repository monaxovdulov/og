from __future__ import annotations
from typing import NamedTuple, Callable, Sequence, Final
import logging

from telebot.types import CallbackQuery
from .core import bot, logger
from .keyboards import NS_MENU, NS_PLAY, NS_TOPICS, NS_SETTINGS, NS_QUESTION, NS_NAV
from .handlers import *

# точная константа для noop
NS_NOOP: Final[str] = "noop"

# === 1) Парсер callback_data ===
class CB(NamedTuple):
    ns: str
    action: str
    args: tuple[str, ...]


def parse_cb(data: str | None) -> CB:
    """
    Parse "<ns>:<action>[:<arg>...]".
    Любые аномалии -> мягко в 'noop'.
    """
    if not data:
        return CB(NS_NOOP, NS_NOOP, ())
    parts = data.split(":")
    ns = parts[0] or NS_NOOP
    action = parts[1] if len(parts) > 1 and parts[1] else NS_NOOP
    args: tuple[str, ...] = tuple(p for p in parts[2:] if p) if len(parts) > 2 else ()
    return CB(ns, action, args)

# === 2) Контекст ===
class Ctx(NamedTuple):
    bot: "TeleBot"
    call: CallbackQuery
    user_id: int
    chat_id: int
    message_id: int

def make_ctx(call: CallbackQuery) -> Ctx:
    msg = call.message
    return Ctx(
        bot=bot,
        call=call,
        user_id=call.from_user.id,
        chat_id=msg.chat.id if msg else 0,
        message_id=msg.message_id if msg else 0,
    )

# === 2.1) Утилиты безопасного парса ===
def parse_positive_int(value: str | None, *, default: int = 1, minimum: int = 1) -> int:
    if value is None:
        return default
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return v if v >= minimum else minimum

def pick_or_default(value: str | None, allowed: set[str], default: str) -> str:
    return value if (value is not None and value in allowed) else default

# === 3) Подроутеры ===
def m_router(action: str, args: Sequence[str], ctx: Ctx) -> None:
    if action == "play":
        handle_m_play(ctx)
    elif action == "rating":
        handle_m_rating(ctx)
    elif action == "settings":
        handle_m_settings(ctx)
    elif action == "topics":
        handle_m_topics(ctx)
    elif action == "help":
        handle_m_help(ctx)
    else:
        handle_unknown(ctx)

def p_router(action: str, args: Sequence[str], ctx: Ctx) -> None:
    if action == "rnd":
        start_random_single(ctx)
    elif action == "series":
        start_series(ctx)
    elif action == "daily":
        start_daily(ctx)
    elif action == "resume":
        resume_series(ctx)
    elif action == "topic":
        topic_id = args[0] if args else ""
        start_topic_series(ctx, topic_id)
    else:
        handle_unknown(ctx)

def t_router(action: str, args: Sequence[str], ctx: Ctx) -> None:
    if action == "page":
        page = parse_positive_int(args[0] if args else None, default=1, minimum=1)
        show_topics_page(ctx, page)
    else:
        handle_unknown(ctx)

def s_router(action: str, args: Sequence[str], ctx: Ctx) -> None:
    if action == "qcount":
        q = parse_positive_int(args[0] if args else None, default=5, minimum=1)
        q = 3 if q <= 3 else 5 if q <= 5 else 10
        set_qcount(ctx, q); refresh_settings_ui(ctx)
    elif action == "diff":
        d = pick_or_default(args[0] if args else None, {"e","m","h"}, "m")
        set_diff(ctx, d);   refresh_settings_ui(ctx)
    elif action == "sol":
        s = pick_or_default(args[0] if args else None, {"imm","end"}, "imm")
        set_solution_mode(ctx, s); refresh_settings_ui(ctx)
    else:
        handle_unknown(ctx)

def q_router(action: str, args: Sequence[str], ctx: Ctx) -> None:
    match action:
        case "solution":  show_solution(ctx)
        case "next":      go_next(ctx)
        case "finish":    finish_series(ctx)
        case "skip_yes":  confirm_skip_yes(ctx)
        case "skip_no":   confirm_skip_no(ctx)
        case _:           handle_unknown(ctx)

def nav_router(action: str, args: Sequence[str], ctx: Ctx) -> None:
    if action == "back":
        go_back(ctx)
    elif action == "home":
        go_home(ctx)
    else:
        handle_unknown(ctx)

# Таблица роутеров
from typing import Callable as _Callable
Handler = _Callable[[str, Sequence[str], Ctx], None]
ROUTERS: dict[str, Handler] = {
    NS_MENU: m_router,
    NS_PLAY: p_router,
    NS_TOPICS: t_router,
    NS_SETTINGS: s_router,
    NS_QUESTION: q_router,
    NS_NAV: nav_router,
}

# === 4) Центральный обработчик ===
from telebot import TeleBot as _TeleBot  # для NamedTuple forward ref

@bot.callback_query_handler(func=lambda c: True)
def on_callback(call: CallbackQuery) -> None:
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.debug("answer_callback_query failed: %r", e)

    route = parse_cb(call.data)
    ctx = make_ctx(call)

    try:
        router = ROUTERS.get(route.ns)
        if router is None or route.ns == NS_NOOP:
            handle_unknown(ctx)
            return
        router(route.action, route.args, ctx)
    except Exception:
        logger.exception(
            "Callback handling error: ns=%r action=%r args=%r", route.ns, route.action, route.args
        )
        try:
            bot.answer_callback_query(call.id, text="Ошибка обработки")
        except Exception:
            pass
