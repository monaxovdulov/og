# app/repo.py
from __future__ import annotations
import json, os, time, random
from typing import TypedDict, Literal, Any

# ---- Типы (минимум) ----
Difficulty = Literal["e", "m", "h"]
AnswerFormat = Literal["single_choice", "multi_choice", "numeric", "text"]

class Topic(TypedDict):
    id: str
    title: str
    emoji: str

class Question(TypedDict, total=False):
    id: str
    title: str
    topic_ids: list[str]
    difficulty: Difficulty
    answer_format: AnswerFormat
    statement: str
    question: str
    correct_answer: Any
    solution_explanation: str
    options: list[str]  # только для choice-типов (если есть)

# users.json — плоская v1
class UserPrefs(TypedDict):
    qcount: int
    diff: Difficulty
    sol: Literal["imm", "end"]

class AwaitInput(TypedDict):
    qid: str
    format: Literal["numeric", "text"]

class AnswerRec(TypedDict, total=False):
    format: AnswerFormat
    value: Any          # text/number/индексы
    is_correct: bool

class Session(TypedDict, total=False):
    mode: Literal["single", "series", "daily"]
    topic_id: str | None
    question_ids: list[str]
    index: int
    answers: dict[str, AnswerRec]
    await_input: AwaitInput | None
    solutions_qids: list[str]

class StatsBucket(TypedDict):
    answered: int
    correct: int

class UserRow(TypedDict, total=False):
    username: str | None
    created_at: str
    updated_at: str
    prefs: UserPrefs
    session: Session | None
    last_topic_id: str | None
    stats: dict[str, Any]

DEFAULT_PREFS: UserPrefs = {"qcount": 5, "diff": "m", "sol": "imm"}

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _atomic_write(path: str, data: Any) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

class Repo:
    """
    Простой репозиторий данных:
    - topics/questions грузим 1 раз на старте (только чтение),
    - users читаем и пишем по мере изменений.
    Без лишней абстракции: всё — dict/list.
    """
    def __init__(
        self,
        topics_path: str = "database/topics.json",
        questions_path: str = "database/questions.json",
        users_path: str = "database/users.json",
    ) -> None:
        self.topics_path = topics_path
        self.questions_path = questions_path
        self.users_path = users_path

        self.topics: list[Topic] = []
        self.topics_by_id: dict[str, Topic] = {}
        self.questions: list[Question] = []
        self.q_by_id: dict[str, Question] = {}
        self.q_by_topic: dict[str, list[Question]] = {}
        self.q_by_topic_diff: dict[tuple[str, str], list[Question]] = {}

        self.users_doc: dict[str, Any] = {"version": "users.v1", "updated_at": _now_iso(), "users": {}}
        self.users: dict[str, UserRow] = self.users_doc["users"]

    # ---- загрузка банка ----
    def load_bank(self) -> None:
        # topics
        tdoc = _read_json(self.topics_path)
        self.topics = list(tdoc.get("topics", []))
        self.topics_by_id = {t["id"]: t for t in self.topics}

        # questions
        qlist = _read_json(self.questions_path)
        if not isinstance(qlist, list):
            raise RuntimeError("questions.json должен быть массивом вопросов")
        self.questions = qlist
        self.q_by_id = {q["id"]: q for q in qlist}

        # индексы по теме/сложности
        self.q_by_topic.clear()
        self.q_by_topic_diff.clear()
        for q in qlist:
            for t in q.get("topic_ids", []):
                self.q_by_topic.setdefault(t, []).append(q)
                self.q_by_topic_diff.setdefault((t, q.get("difficulty", "m")), []).append(q)

        # валидация ссылок вопрос→тема (простая)
        bad = [q["id"] for q in qlist if any(t not in self.topics_by_id for t in q.get("topic_ids", []))]
        if bad:
            raise RuntimeError(f"Вопросы с несуществующими topic_ids: {bad}")

    # ---- users ----
    def load_users(self) -> None:
        # допускаем пустой/несуществующий файл
        if not os.path.exists(self.users_path):
            self.users_doc = {"version": "users.v1", "updated_at": _now_iso(), "users": {}}
            self.users = self.users_doc["users"]
            self.save_users()
            return
        try:
            data = _read_json(self.users_path)
        except Exception:
            # если файл пуст/бит — начинаем заново (можно логировать)
            data = {}
        if not isinstance(data, dict) or "users" not in data:
            data = {"version": "users.v1", "updated_at": _now_iso(), "users": {}}
        self.users_doc = data
        self.users = self.users_doc["users"]

    def save_users(self) -> None:
        self.users_doc["updated_at"] = _now_iso()
        _atomic_write(self.users_path, self.users_doc)

    # ---- API для бота ----
    def get_topics(self) -> list[Topic]:
        return self.topics

    def ensure_user(self, user_id: int, username: str | None = None) -> UserRow:
        key = str(user_id)
        u = self.users.get(key)
        if u is None:
            now = _now_iso()
            u = {
                "username": username,
                "created_at": now,
                "updated_at": now,
                "prefs": dict(DEFAULT_PREFS),
                "session": None,
                "last_topic_id": None,
                "stats": {"total": {"answered": 0, "correct": 0}, "by_topic": {}},
            }
            self.users[key] = u
            self.save_users()
        return u

    def update_prefs(self, user_id: int, **changes) -> None:
        u = self.ensure_user(user_id)
        u["prefs"].update(changes)
        u["updated_at"] = _now_iso()
        self.save_users()

    def pick_series(self, topic_id: str | None, diff: Difficulty, count: int) -> list[Question]:
        # фильтрация
        if topic_id:
            pool = [q for q in self.q_by_topic.get(topic_id, []) if q.get("difficulty") == diff]
        else:
            pool = [q for q in self.questions if q.get("difficulty") == diff]
        if len(pool) < count:
            return []
        return random.sample(pool, count)

    def start_session(self, user_id: int, *, mode: str, topic_id: str | None, diff: Difficulty, count: int) -> list[Question]:
        u = self.ensure_user(user_id)
        series = self.pick_series(topic_id, diff, count)
        if not series:
            return []
        qids = [q["id"] for q in series]
        u["session"] = {
            "mode": mode, "topic_id": topic_id, "question_ids": qids,
            "index": 0, "answers": {}, "await_input": None, "solutions_qids": []
        }
        u["last_topic_id"] = topic_id
        u["updated_at"] = _now_iso()
        self.save_users()
        return series

    def get_current_question(self, user_id: int) -> Question | None:
        u = self.ensure_user(user_id)
        s = u.get("session")
        if not s:
            return None
        idx = s.get("index", 0)
        qids = s.get("question_ids", [])
        if 0 <= idx < len(qids):
            return self.q_by_id.get(qids[idx])
        return None

    def record_answer(self, user_id: int, qid: str, rec: AnswerRec, *, topic_hint: str | None = None) -> None:
        u = self.ensure_user(user_id)
        s = u.get("session")
        if not s:
            return
        s["answers"][qid] = rec
        # stats
        t = topic_hint
        if t is None:
            t = self.q_by_id.get(qid, {}).get("topic_ids", [None])[0]
        total = u["stats"]["total"]
        total["answered"] += 1
        if rec.get("is_correct"):
            total["correct"] += 1
        if t:
            by = u["stats"]["by_topic"].setdefault(t, {"answered": 0, "correct": 0})
            by["answered"] += 1
            if rec.get("is_correct"):
                by["correct"] += 1
        u["updated_at"] = _now_iso()
        self.save_users()

    def advance(self, user_id: int) -> bool:
        """Сдвинуться к следующему вопросу. Возвращает True, если серия ещё идёт."""
        u = self.ensure_user(user_id)
        s = u.get("session")
        if not s:
            return False
        s["index"] += 1
        more = s["index"] < len(s.get("question_ids", []))
        u["updated_at"] = _now_iso()
        self.save_users()
        return more

    def finish(self, user_id: int) -> None:
        u = self.ensure_user(user_id)
        u["session"] = None
        u["updated_at"] = _now_iso()
        self.save_users()

    # удобство для numeric/text ввода
    def set_await_input(self, user_id: int, qid: str, fmt: Literal["numeric", "text"]) -> None:
        u = self.ensure_user(user_id)
        s = u.get("session")
        if not s:
            return
        s["await_input"] = {"qid": qid, "format": fmt}
        u["updated_at"] = _now_iso()
        self.save_users()

    def clear_await_input(self, user_id: int) -> None:
        u = self.ensure_user(user_id)
        s = u.get("session")
        if not s:
            return
        s["await_input"] = None
        u["updated_at"] = _now_iso()
        self.save_users()
