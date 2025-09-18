from __future__ import annotations
from typing import Final
from telebot.apihelper import ApiTelegramException
from .core import bot, logger
from .keyboards import (
    kb_main_menu, kb_play_menu, kb_settings_menu, kb_topics_page,
    kb_question_controls, kb_confirm_skip, kb_results,
    NS_MENU, NS_PLAY, NS_TOPICS, NS_SETTINGS, NS_QUESTION, NS_NAV,
    Topic, Prefs,
)

# --- In-memory "repos" (примитивные для демо) ---
PREFS: dict[int, Prefs] = {}
LAST_TOPIC_BY_USER: dict[int, str] = {}
HAS_RESUME: dict[int, bool] = {}  # есть ли незавершённая серия

# демо-банк тем
ALL_TOPICS: list[Topic] = [
    {"id": "py-basics", "title": "Python основы", "emoji": "🐍"},
    {"id": "alg", "title": "Алгоритмы", "emoji": "🧠"},
    {"id": "db", "title": "Базы данных", "emoji": "🗄"},
    {"id": "net", "title": "Сети", "emoji": "🌐"},
    {"id": "os", "title": "ОС", "emoji": "🖥"},
    {"id": "linux", "title": "Linux", "emoji": "🐧"},
    {"id": "git", "title": "Git", "emoji": "🌳"},
    {"id": "tlgrm", "title": "Telegram", "emoji": "✉️"},
    {"id": "async", "title": "Async", "emoji": "⚡"},
    {"id": "tests", "title": "Тесты", "emoji": "✅"},
]

# --- UI helpers ---
def _reply_user_id(ctx) -> int:
    # если нет chat_id (inline), шлём в личку по user_id
    return ctx.chat_id or ctx.user_id

def _is_not_modified(err: Exception) -> bool:
    """True, если Telegram вернул 'message is not modified' (для текста или markup)."""
    if not isinstance(err, ApiTelegramException):
        return False
    desc = (getattr(err, "description", "") or "").lower()
    # встречаются варианты формулировки
    return "message is not modified" in desc or "message not modified" in desc

def _safe_edit_text(ctx, *, text: str, reply_markup=None) -> None:
    """
    Пытается отредактировать исходное сообщение; если нельзя — отправляем новое.
    """
    if ctx.chat_id and ctx.message_id:
        try:
            bot.edit_message_text(
                text=text, chat_id=ctx.chat_id, message_id=ctx.message_id, reply_markup=reply_markup
            )
            return
        except Exception as e:
            # если содержимое не меняется — просто выходим без дубляжа сообщений
            if _is_not_modified(e):
                logger.debug("skip send: message is not modified")
                return
            # прочие причины — падаем в fallback (например, 'message to edit not found')
            logger.debug("edit_message_text failed, fallback to send: %r", e)
    bot.send_message(_reply_user_id(ctx), text, reply_markup=reply_markup)

def _safe_edit_kb(ctx, *, reply_markup) -> None:
    """
    Меняем только клавиатуру; если нельзя — пересылаем тот же текст с новой клавиатурой.
    """
    if ctx.chat_id and ctx.message_id:
        try:
            bot.edit_message_reply_markup(chat_id=ctx.chat_id, message_id=ctx.message_id, reply_markup=reply_markup)
            return
        except Exception as e:
            if _is_not_modified(e):
                logger.debug("skip send: reply_markup is not modified")
                return
            logger.debug("edit_message_reply_markup failed, fallback to send: %r", e)
    # fallback: отправим пустой текст с клавиатурой
    bot.send_message(_reply_user_id(ctx), "Обновлено", reply_markup=reply_markup)

def _get_prefs(user_id: int) -> Prefs:
    return PREFS.setdefault(user_id, {"qcount": 5, "diff": "m", "sol": "imm"})

# --- Menu handlers ---
def handle_m_play(ctx) -> None:
    has_resume = HAS_RESUME.get(ctx.user_id, False)
    _safe_edit_text(ctx, text="<b>Играть</b>", reply_markup=kb_play_menu(has_resume=has_resume))

def handle_m_rating(ctx) -> None:
    _safe_edit_text(ctx, text="<b>Рейтинг</b>\nСкоро здесь будет рейтинг.", reply_markup=kb_main_menu())

def handle_m_settings(ctx) -> None:
    prefs = _get_prefs(ctx.user_id)
    _safe_edit_text(ctx, text="<b>Настройки</b>", reply_markup=kb_settings_menu(prefs=prefs))

def handle_m_topics(ctx) -> None:
    _safe_edit_text(ctx, text="<b>Темы</b>", reply_markup=kb_topics_page(topics=ALL_TOPICS, page=1))

def handle_m_help(ctx) -> None:
    _safe_edit_text(ctx, text="Помощь: жмите кнопки 🙂", reply_markup=kb_main_menu())

def handle_unknown(ctx) -> None:
    _safe_edit_text(ctx, text="Не понимаю эту кнопку 🤔", reply_markup=kb_main_menu())

# --- Play handlers ---
def start_random_single(ctx) -> None:
    HAS_RESUME[ctx.user_id] = True
    _safe_edit_text(ctx, text="🎲 Стартуем одиночный вопрос", reply_markup=kb_question_controls(has_next=True, in_series=False))

def start_series(ctx) -> None:
    HAS_RESUME[ctx.user_id] = True
    _safe_edit_text(ctx, text="🧩 Старт серии вопросов", reply_markup=kb_question_controls(has_next=True, in_series=True))

def start_daily(ctx) -> None:
    HAS_RESUME[ctx.user_id] = True
    _safe_edit_text(ctx, text="📆 Дневное задание", reply_markup=kb_question_controls(has_next=True, in_series=False))

def resume_series(ctx) -> None:
    _safe_edit_text(ctx, text="⏸ Продолжаем серию", reply_markup=kb_question_controls(has_next=True, in_series=True))

def start_topic_series(ctx, topic_id: str) -> None:
    LAST_TOPIC_BY_USER[ctx.user_id] = topic_id
    HAS_RESUME[ctx.user_id] = True
    title = next((t["title"] for t in ALL_TOPICS if t["id"] == topic_id), "Тема")
    _safe_edit_text(ctx, text=f"▶️ Начинаем тему: <b>{title}</b>", reply_markup=kb_question_controls(has_next=True, in_series=True))

def show_topics_page(ctx, page: int) -> None:
    _safe_edit_kb(ctx, reply_markup=kb_topics_page(topics=ALL_TOPICS, page=page))

# --- Settings handlers ---
def set_qcount(ctx, q: int) -> None:
    prefs = _get_prefs(ctx.user_id); prefs["qcount"] = q

def set_diff(ctx, d: str) -> None:
    prefs = _get_prefs(ctx.user_id); prefs["diff"] = d

def set_solution_mode(ctx, s: str) -> None:
    prefs = _get_prefs(ctx.user_id); prefs["sol"] = s

def refresh_settings_ui(ctx) -> None:
    prefs = _get_prefs(ctx.user_id)
    _safe_edit_kb(ctx, reply_markup=kb_settings_menu(prefs=prefs))

# --- Question flow ---
def show_solution(ctx) -> None:
    _safe_edit_text(ctx, text="🧠 Решение:\n<i>Пояснение к ответу...</i>", reply_markup=kb_question_controls(has_next=True, in_series=True))

def go_next(ctx) -> None:
    _safe_edit_text(ctx, text="Следующий вопрос →", reply_markup=kb_question_controls(has_next=True, in_series=True))

def finish_series(ctx) -> None:
    HAS_RESUME[ctx.user_id] = False
    topic_id = LAST_TOPIC_BY_USER.get(ctx.user_id)
    _safe_edit_text(ctx, text="Итоги серии ✅", reply_markup=kb_results(topic_id))

def confirm_skip_yes(ctx) -> None:
    _safe_edit_text(ctx, text="Вопрос пропущен ↷", reply_markup=kb_question_controls(has_next=True, in_series=True))

def confirm_skip_no(ctx) -> None:
    _safe_edit_text(ctx, text="Ок, продолжаем", reply_markup=kb_question_controls(has_next=True, in_series=True))

# --- Navigation ---
def go_back(ctx) -> None:
    # для демо "Назад" = "Домой"
    go_home(ctx)

def go_home(ctx) -> None:
    _safe_edit_text(ctx, text="<b>Главное меню</b>", reply_markup=kb_main_menu())
