"""
Inline Keyboards for our Telegram quiz bot (telebot/pyTelegramBotAPI).
Python >= 3.12, type-annotated, self-documenting.

Design notes:
- Callback schema is compact and consistent: "<ns>:<action>[:<arg>...]".
- Keep callback_data under Telegram's 64-byte limit (bytes).
- Each function renders a single "screen" of our UX.

Namespace legend:
    m   -> menu
    p   -> play
    t   -> topics
    s   -> settings
    q   -> question
    nav -> navigation
"""
from __future__ import annotations
from typing import TypedDict, NotRequired, Literal, Iterable, Final
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== Domain types =====
class Topic(TypedDict):
    id: str
    title: str
    emoji: NotRequired[str]

class Prefs(TypedDict):
    qcount: int                  # 3|5|10
    diff: Literal["e", "m", "h"] # easy|medium|hard
    sol: Literal["imm", "end"]   # immediately / at the end

# ===== Namespace constants =====
NS_MENU: Final[str] = "m"
NS_PLAY: Final[str] = "p"
NS_TOPICS: Final[str] = "t"
NS_SETTINGS: Final[str] = "s"
NS_QUESTION: Final[str] = "q"
NS_NAV: Final[str] = "nav"

# ===== Callback builder =====
MAX_CB_BYTES: Final[int] = 64

def cb(ns: str, action: str, *args: str | int) -> str:
    """
    Build compact callback_data string: "<ns>:<action>[:<arg>...]".

    Args:
        ns: Namespace short code (e.g. 'm','p','t','s','q','nav'). No ':'.
        action: Domain action (e.g. 'play','topic','page'). No ':'.
        *args: Extra pieces (str|int). No ':'.

    Returns:
        UTF-8 string < MAX_CB_BYTES bytes.

    Raises:
        ValueError: if contains ':' or exceeds byte limit.
    """
    parts: list[str] = [ns, action, *map(str, args)]
    for i, p in enumerate(parts):
        if ":" in p:
            raise ValueError(f"':' is not allowed in callback pieces; got {p!r} at index {i}")
    data: str = ":".join(parts)
    size = len(data.encode("utf-8"))
    if size > MAX_CB_BYTES:
        raise ValueError(
            f"callback_data exceeds {MAX_CB_BYTES} bytes ({size}): {data!r}. "
            f"Keep it compact."
        )
    return data

# ===== Tiny UI helpers =====
def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)

def _mark_active(text: str, active: bool) -> str:
    return f"● {text}" if active else text

def _kb(rows: Iterable[Iterable[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    for row in rows:
        m.row(*row)
    return m

def _nav_row() -> list[InlineKeyboardButton]:
    return [
        _btn("← Назад", cb(NS_NAV, "back")),
        _btn("🏠 Меню", cb(NS_NAV, "home")),
    ]

# ===== Main menu =====
def kb_main_menu() -> InlineKeyboardMarkup:
    top = [
        _btn("▶️ Играть",  cb(NS_MENU, "play")),
        _btn("🏆 Рейтинг", cb(NS_MENU, "rating")),
        _btn("⚙️ Настройки", cb(NS_MENU, "settings")),
    ]
    bottom = [
        _btn("📚 Темы", cb(NS_MENU, "topics")),
        _btn("❓ Помощь", cb(NS_MENU, "help")),
    ]
    return _kb([top, bottom])

# ===== Play =====
def kb_play_menu(*, has_resume: bool) -> InlineKeyboardMarkup:
    row1 = [
        _btn("🎲 Случайный", cb(NS_PLAY, "rnd")),
        _btn("🧩 Серия", cb(NS_PLAY, "series")),
        _btn("📆 Дневное", cb(NS_PLAY, "daily")),
    ]
    row2: list[InlineKeyboardButton] = []
    if has_resume:
        row2.append(_btn("⏸ Продолжить", cb(NS_PLAY, "resume")))
    row2.append(_btn("📚 По теме", cb(NS_MENU, "topics")))
    return _kb([row1, row2, _nav_row()])

# ===== Topics (paged grid) =====
def kb_topics_page(*, topics: list[Topic], page: int, per_page: int = 8) -> InlineKeyboardMarkup:
    if page < 1:
        raise ValueError(f"page must start from 1, got {page}")
    if per_page <= 0 or per_page % 2 != 0:
        raise ValueError(f"per_page must be a positive even number, got {per_page}")

    start = (page - 1) * per_page
    chunk = topics[start:start + per_page]

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for t in chunk:
        title = f"{t.get('emoji', '')} {t['title']}".strip()
        row.append(_btn(title, cb(NS_PLAY, "topic", t["id"])))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav_page: list[InlineKeyboardButton] = []
    if page > 1:
        nav_page.append(_btn("⬅️", cb(NS_TOPICS, "page", page - 1)))
    if start + per_page < len(topics):
        nav_page.append(_btn("➡️", cb(NS_TOPICS, "page", page + 1)))
    if nav_page:
        rows.append(nav_page)

    rows.append(_nav_row())
    return _kb(rows)

# ===== Settings =====
def kb_settings_menu(*, prefs: Prefs) -> InlineKeyboardMarkup:
    q = prefs.get("qcount", 5)
    d = prefs.get("diff", "m")
    sol = prefs.get("sol", "imm")

    row_q = [
        _btn(_mark_active("3", q == 3), cb(NS_SETTINGS, "qcount", 3)),
        _btn(_mark_active("5", q == 5), cb(NS_SETTINGS, "qcount", 5)),
        _btn(_mark_active("10", q == 10), cb(NS_SETTINGS, "qcount", 10)),
    ]
    row_d = [
        _btn(_mark_active("Лёгк", d == "e"), cb(NS_SETTINGS, "diff", "e")),
        _btn(_mark_active("Сред", d == "m"), cb(NS_SETTINGS, "diff", "m")),
        _btn(_mark_active("Слож", d == "h"), cb(NS_SETTINGS, "diff", "h")),
    ]
    row_sol = [
        _btn(_mark_active("Сразу", sol == "imm"), cb(NS_SETTINGS, "sol", "imm")),
        _btn(_mark_active("В конце", sol == "end"), cb(NS_SETTINGS, "sol", "end")),
    ]
    return _kb([row_q, row_d, row_sol, _nav_row()])

# ===== Question controls =====
def kb_question_controls(*, has_next: bool, in_series: bool) -> InlineKeyboardMarkup:
    row1: list[InlineKeyboardButton] = [_btn("🧠 Решение", cb(NS_QUESTION, "solution"))]
    if has_next:
        row1.append(_btn("Дальше →", cb(NS_QUESTION, "next")))
    else:
        row1.append(_btn("Завершить серию", cb(NS_QUESTION, "finish")) if in_series
                    else _btn("Завершить", cb(NS_QUESTION, "finish")))
    row2 = [_btn("🏠 Меню", cb(NS_NAV, "home"))]
    return _kb([row1, row2])

# ===== Skip confirm =====
def kb_confirm_skip() -> InlineKeyboardMarkup:
    row = [
        _btn("Пропустить — да", cb(NS_QUESTION, "skip_yes")),
        _btn("Нет, вернуться", cb(NS_QUESTION, "skip_no")),
    ]
    return _kb([row])

# ===== Results =====
def kb_results(topic_id: str | None) -> InlineKeyboardMarkup:
    row1: list[InlineKeyboardButton] = []
    if topic_id:
        row1.append(_btn("Ещё по теме", cb(NS_PLAY, "topic", topic_id)))
    row1.append(_btn("Играть ещё", cb(NS_MENU, "play")))
    row2 = [
        _btn("Другая тема", cb(NS_MENU, "topics")),
        _btn("🏠 Меню", cb(NS_NAV, "home")),
    ]
    return _kb([row1, row2])
