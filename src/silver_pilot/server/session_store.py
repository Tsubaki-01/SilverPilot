"""
模块名称：session_store
功能描述：会话元数据的内存存储（开发环境回退方案）。
         方法命名与 RedisStore 对齐，可互相替换。

注意：生产环境应使用 RedisStore。
"""

import time
import uuid
from typing import Any

from .models import MessageRecord, SessionMeta


class SessionStore:
    """
    会话元数据内存存储。

    使用示例::

        store = SessionStore()
        meta = store.create("药品咨询", user_id="user_001")
        store.add_message(meta.session_id, MessageRecord(role="user", content="你好"))
        sessions = store.list_sessions("user_001")
    """

    def __init__(self) -> None:
        # session_id → SessionMeta
        self._sessions: dict[str, SessionMeta] = {}
        # session_id → list[MessageRecord]
        self._messages: dict[str, list[MessageRecord]] = {}
        self._profiles: dict[str, dict[str, Any]] = {}

    # ── 会话管理 ──

    def create_session(self, name: str = "新对话", user_id: str = "default_user") -> SessionMeta:
        sid = uuid.uuid4().hex[:12]
        now = time.time()
        meta = SessionMeta(
            session_id=sid,
            name=name,
            created_at=now,
            updated_at=now,
            message_count=0,
            user_id=user_id,
        )
        self._sessions[sid] = meta
        self._messages[sid] = []
        self.add_message(
            sid,
            MessageRecord(
                role="assistant", content="您好！我是小银，您的健康助手。有什么可以帮您的吗？"
            ),
        )
        return meta

    def get_session(self, session_id: str) -> SessionMeta | None:
        return self._sessions.get(session_id)

    def list_sessions(self, user_id: str = "default_user") -> list[SessionMeta]:
        sessions = [s for s in self._sessions.values() if s.user_id == user_id]
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._messages.pop(session_id, None)
            return True
        return False

    def add_message(self, session_id: str, message: MessageRecord) -> None:
        if session_id not in self._messages:
            self._messages[session_id] = []
        self._messages[session_id].append(message)
        meta = self._sessions.get(session_id)
        if meta:
            meta.message_count = len(self._messages[session_id])
            meta.updated_at = time.time()
            if meta.name == "新对话" and message.role == "user":
                meta.name = message.content[:15]

    def get_messages(self, session_id: str) -> list[MessageRecord]:
        return self._messages.get(session_id, [])

    # ── 用户画像（简单字典实现，兼容 RedisStore 接口）──

    def get_profile(self, user_id: str) -> dict[str, Any]:
        if user_id in self._profiles:
            return self._profiles[user_id]
        profile = {
            "user_id": user_id,
            "chronic_diseases": [],
            "allergies": [],
            "current_medications": [],
        }
        self._profiles[user_id] = profile
        return profile

    def update_profile(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        profile = self.get_profile(user_id)
        for k, v in updates.items():
            if isinstance(v, list) and isinstance(profile.get(k), list):
                for item in v:
                    if item not in profile[k]:
                        profile[k].append(item)
            else:
                profile[k] = v
        return profile

    def delete_profile(self, user_id: str) -> bool:
        return bool(self._profiles.pop(user_id, None))
