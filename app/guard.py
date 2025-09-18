from __future__ import annotations
import time
import threading
from typing import Final, Tuple, Dict, Set, Optional
from telebot.types import CallbackQuery

class CallbackShield:
    """
    Anti-bounce + in-flight guard for callback_query.
    - Dedup: блокирует повтор того же (user, chat, message, data) в dedup_ttl.
    - In-flight: сереализует обработку колбэков на пользователя в small window.
    """
    def __init__(self, *, dedup_ttl: float = 0.8, in_flight_timeout: float = 2.0) -> None:
        self.dedup_ttl: Final[float] = dedup_ttl
        self.in_flight_timeout: Final[float] = in_flight_timeout
        self._last: Dict[Tuple[int, int, int, str], float] = {}
        self._inflight: Dict[int, float] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(call: CallbackQuery) -> Tuple[int, int, int, str]:
        msg = call.message
        chat_id = msg.chat.id if msg else 0
        msg_id = msg.message_id if msg else 0
        data = call.data or ""
        return (call.from_user.id, chat_id, msg_id, data)

    def is_duplicate(self, call: CallbackQuery) -> bool:
        """True, если тот же самый колбэк пришёл слишком быстро подряд."""
        k = self._key(call)
        now = time.monotonic()
        with self._lock:
            ts = self._last.get(k)
            self._last[k] = now
            return ts is not None and (now - ts) < self.dedup_ttl

    def try_acquire(self, user_id: int) -> bool:
        """
        Ставит 'занято' на пользователя. Повторная попытка до таймаута — False.
        """
        now = time.monotonic()
        with self._lock:
            ts = self._inflight.get(user_id)
            if ts is not None and (now - ts) < self.in_flight_timeout:
                return False
            self._inflight[user_id] = now
            return True

    def release(self, user_id: int) -> None:
        """Снимает 'занято' с пользователя (всегда в finally!)."""
        with self._lock:
            self._inflight.pop(user_id, None)
