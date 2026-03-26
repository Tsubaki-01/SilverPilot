"""
模块名称：redis_store
功能描述：基于 Redis 的统一存储层，提供用户画像管理和会话管理两大能力。
         替代原有的 SQLite (UserProfileManager) 和内存字典 (SessionStore)。

数据结构设计：
    用户画像:
        - Key: "profile:{user_id}"  → JSON string

    会话管理:
        - Key: "session:{session_id}:meta"     → JSON (SessionMeta)
        - Key: "session:{session_id}:messages"  → Redis List (每项为 JSON MessageRecord)
        - Key: "user_sessions:{user_id}"        → Redis Sorted Set (member=session_id, score=updated_at)

生产优势：
    - 原子操作，多进程/多实例安全
    - 数据自动持久化（RDB/AOF）
    - 可设置 TTL 自动清理过期会话
    - 支持发布/订阅扩展实时通知
"""

import json
import time
import uuid
from typing import Any

import redis

from silver_pilot.config import config
from silver_pilot.utils import get_channel_logger

from .models import MessageRecord, SessionMeta

# ================= 日志 =================
logger = get_channel_logger(config.LOG_DIR / "server", "redis_store")

# ================= 默认配置 =================
DEFAULT_REDIS_HOST: str = getattr(config, "REDIS_HOST", "localhost")
DEFAULT_REDIS_PORT: int = int(getattr(config, "REDIS_PORT", 6379))
DEFAULT_REDIS_DB: int = int(getattr(config, "REDIS_DB", 0))
DEFAULT_REDIS_PASSWORD: str | None = getattr(config, "REDIS_PASSWORD", None) or None
DEFAULT_SESSION_TTL: int = int(getattr(config, "SESSION_TTL_SECONDS", 86400 * 30))  # 30天

# ================= Key 前缀 =================
PROFILE_PREFIX = "profile:"
SESSION_META_PREFIX = "session:"
SESSION_META_SUFFIX = ":meta"
SESSION_MSG_PREFIX = "session:"
SESSION_MSG_SUFFIX = ":messages"
USER_SESSIONS_PREFIX = "user_sessions:"

# ================= 默认画像模板 =================
DEFAULT_PROFILE: dict[str, Any] = {
    "user_id": "",
    "chronic_diseases": [],
    "allergies": [],
    "current_medications": [],
    "emergency_contacts": [],
    "preferred_dialect": "",
    "interaction_patterns": {
        "active_hours": "6:00-21:00",
        "avg_session_turns": 0,
    },
    "created_at": "",
    "updated_at": "",
}


class RedisStore:
    """
    基于 Redis 的统一存储层。

    提供两大功能模块：
    1. **用户画像管理** — 替代原 UserProfileManager (SQLite)
    2. **会话管理** — 替代原 SessionStore (内存字典)

    使用示例::

        store = RedisStore()

        # 用户画像
        profile = store.get_profile("user_001")
        store.update_profile("user_001", {"chronic_diseases": ["高血压"]})

        # 会话管理
        meta = store.create_session("药品咨询", user_id="user_001")
        store.add_message(meta.session_id, MessageRecord(role="user", content="你好"))
        sessions = store.list_sessions("user_001")
    """

    def __init__(
        self,
        host: str = DEFAULT_REDIS_HOST,
        port: int = DEFAULT_REDIS_PORT,
        db: int = DEFAULT_REDIS_DB,
        password: str | None = DEFAULT_REDIS_PASSWORD,
        session_ttl: int = DEFAULT_SESSION_TTL,
    ) -> None:
        """
        初始化 Redis 存储客户端。

        Args:
            host: Redis 主机地址。
            port: Redis 端口。
            db: Redis 数据库编号。
            password: Redis 认证密码，可为空。
            session_ttl: 会话相关 Key 的 TTL（秒），小于等于 0 表示不设置过期。

        Returns:
            None

        Raises:
            redis.ConnectionError: 当 Redis 不可连接时抛出。
        """
        self.session_ttl = session_ttl
        self._client: redis.Redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        # 连通性测试
        try:
            self._client.ping()
            logger.info(f"Redis 连接成功 | {host}:{port} db={db}")
        except redis.ConnectionError as e:
            logger.error(f"Redis 连接失败: {e}")
            raise

    def _validate_non_empty_str(self, value: Any, field_name: str) -> str:
        """
        校验并标准化非空字符串参数。

        Args:
            value: 待校验的输入值。
            field_name: 字段名，用于构造错误信息。

        Returns:
            str: 去除首尾空白后的合法字符串。

        Raises:
            TypeError: 当 value 不是字符串时抛出。
            ValueError: 当 value 去空白后为空字符串时抛出。
        """
        if not isinstance(value, str):
            raise TypeError(f"{field_name} 必须是字符串")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} 必须是非空字符串")
        return normalized

    # ════════════════════════════════════════════════
    #  用户画像管理（替代 UserProfileManager）
    # ════════════════════════════════════════════════

    def get_profile(self, user_id: str) -> dict[str, Any]:
        """
        获取用户画像。不存在则自动创建默认画像。

        Args:
            user_id: 用户唯一标识

        Returns:
            dict: 用户画像字典
        """
        user_id = self._validate_non_empty_str(user_id, "user_id")

        key = f"{PROFILE_PREFIX}{user_id}"
        raw = self._client.get(key)

        if raw:
            profile = json.loads(raw)
            logger.debug(f"加载用户画像 | user_id={user_id}")
            return profile

        logger.info(f"用户不存在，创建默认画像 | user_id={user_id}")
        return self._create_default_profile(user_id)

    def update_profile(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """
        增量更新用户画像。列表字段合并去重，字典字段深度合并。

        Args:
            user_id: 用户唯一标识
            updates: 需要更新的字段字典

        Returns:
            dict: 更新后的完整画像

        Raises:
            TypeError: 当 updates 不是 dict 时抛出。
        """
        user_id = self._validate_non_empty_str(user_id, "user_id")

        if not isinstance(updates, dict):
            raise TypeError("updates 必须是 dict")

        if not updates:
            return self.get_profile(user_id)

        profile = self.get_profile(user_id)
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        for key, value in updates.items():
            if not isinstance(key, str):
                logger.warning(f"忽略非法画像字段（key 非字符串） | user_id={user_id} | key={key}")
                continue

            if key in ("user_id", "created_at", "updated_at"):
                continue

            existing_value = profile.get(key)

            if existing_value is None:
                profile[key] = value
            elif not isinstance(existing_value, type(value)):
                logger.warning(
                    "类型不匹配字段 | user_id=%s | field=%s | existing_type=%s | new_type=%s",
                    user_id,
                    key,
                    type(existing_value).__name__,
                    type(value).__name__,
                )
                continue
            elif isinstance(existing_value, list) and isinstance(value, list):
                existing = existing_value
                for item in value:
                    if item not in existing:
                        existing.append(item)
                profile[key] = existing
            elif isinstance(existing_value, dict):
                profile[key] = self._deep_merge_dict(existing_value, value)
            else:
                profile[key] = value

        profile["updated_at"] = now
        self._save_profile(user_id, profile)
        logger.info(f"用户画像已更新 | user_id={user_id} | fields={list(updates.keys())}")
        return profile

    def _deep_merge_dict(self, base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        """
        递归合并字典：当双方字段均为 dict 时继续向下合并。

        Args:
            base: 基础字典。
            updates: 需要覆盖或合并的新字典。

        Returns:
            dict: 合并后的新字典，不会原地修改入参 base。
        """
        merged = dict(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge_dict(merged[key], value)
            else:
                merged[key] = value
        return merged

    def delete_profile(self, user_id: str) -> bool:
        """
        删除用户画像。

        Args:
            user_id: 用户唯一标识。

        Returns:
            bool: 删除成功返回 True；不存在或未删除返回 False。
        """
        user_id = self._validate_non_empty_str(user_id, "user_id")

        key = f"{PROFILE_PREFIX}{user_id}"
        deleted = self._client.delete(key)
        if deleted:
            logger.info(f"用户画像已删除 | user_id={user_id}")
        return bool(deleted)

    def _create_default_profile(self, user_id: str) -> dict[str, Any]:
        """
        创建并持久化默认画像。

        Args:
            user_id: 用户唯一标识。

        Returns:
            dict: 默认画像内容。
        """
        user_id = self._validate_non_empty_str(user_id, "user_id")

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        profile = {**DEFAULT_PROFILE, "user_id": user_id, "created_at": now, "updated_at": now}
        self._save_profile(user_id, profile)
        return profile

    def _save_profile(self, user_id: str, profile: dict[str, Any]) -> None:
        """
        将画像序列化后写入 Redis。

        Args:
            user_id: 用户唯一标识。
            profile: 待保存的完整画像字典。

        Returns:
            None

        Raises:
            TypeError: 当 profile 不是 dict 时抛出。
        """
        user_id = self._validate_non_empty_str(user_id, "user_id")

        if not isinstance(profile, dict):
            raise TypeError("profile 必须是 dict")
        key = f"{PROFILE_PREFIX}{user_id}"
        self._client.set(key, json.dumps(profile, ensure_ascii=False))

    # ════════════════════════════════════════════════
    #  会话管理（替代 SessionStore）
    # ════════════════════════════════════════════════

    def create_session(self, name: str = "新对话", user_id: str = "default_user") -> SessionMeta:
        """
        创建新会话并自动添加欢迎消息。

        Args:
            name: 会话名称，传入空白字符串时会回退为“新对话”。
            user_id: 会话所属用户 ID。

        Returns:
            SessionMeta: 创建完成后的会话元数据。

        Raises:
            TypeError: 当 name 不是字符串时抛出。
        """
        user_id = self._validate_non_empty_str(user_id, "user_id")

        if not isinstance(name, str):
            raise TypeError("name 必须是字符串")
        name = name.strip() or "新对话"

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

        meta_key = f"{SESSION_META_PREFIX}{sid}{SESSION_META_SUFFIX}"
        self._client.set(meta_key, meta.model_dump_json())
        if self.session_ttl > 0:
            self._client.expire(meta_key, self.session_ttl)

        # 加入用户的会话索引（Sorted Set，score=更新时间）
        user_key = f"{USER_SESSIONS_PREFIX}{user_id}"
        self._client.zadd(user_key, {sid: now})

        # 添加欢迎消息
        self.add_message(
            sid,
            MessageRecord(
                role="assistant",
                content="您好！我是小银，您的健康助手。有什么可以帮您的吗？",
            ),
        )
        logger.info(f"会话已创建 | session_id={sid} | user_id={user_id}")
        return meta

    def get_session(self, session_id: str) -> SessionMeta | None:
        """
        获取会话元数据。

        Args:
            session_id: 会话 ID。

        Returns:
            SessionMeta | None: 命中时返回会话元数据，未命中返回 None。
        """
        session_id = self._validate_non_empty_str(session_id, "session_id")

        meta_key = f"{SESSION_META_PREFIX}{session_id}{SESSION_META_SUFFIX}"
        raw = self._client.get(meta_key)
        if raw:
            return SessionMeta.model_validate_json(raw)
        return None

    def list_sessions(self, user_id: str = "default_user") -> list[SessionMeta]:
        """
        列出指定用户的所有会话，按更新时间倒序。

        Args:
            user_id: 用户 ID。

        Returns:
            list[SessionMeta]: 会话元数据列表（按 updated_at 降序）。
        """
        user_id = self._validate_non_empty_str(user_id, "user_id")

        user_key = f"{USER_SESSIONS_PREFIX}{user_id}"
        # zrevrange 返回按 score 降序的 member 列表
        raw_ids = self._client.zrevrange(user_key, 0, -1)
        session_ids: list[str] = list(raw_ids) if raw_ids else []

        sessions: list[SessionMeta] = []
        if not session_ids:
            logger.warning(f"用户没有会话 | user_id={user_id}")
        else:
            for sid in session_ids:
                meta = self.get_session(sid)
                if meta:
                    sessions.append(meta)
                else:
                    # 元数据已过期，清理索引
                    self._client.zrem(user_key, sid)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话及其所有消息。

        Args:
            session_id: 会话 ID。

        Returns:
            bool: 删除成功返回 True；会话不存在时返回 False。
        """
        session_id = self._validate_non_empty_str(session_id, "session_id")

        meta = self.get_session(session_id)
        if not meta:
            return False

        pipe = self._client.pipeline()
        pipe.delete(f"{SESSION_META_PREFIX}{session_id}{SESSION_META_SUFFIX}")
        pipe.delete(f"{SESSION_MSG_PREFIX}{session_id}{SESSION_MSG_SUFFIX}")
        pipe.zrem(f"{USER_SESSIONS_PREFIX}{meta.user_id}", session_id)
        pipe.execute()

        logger.info(f"会话已删除 | session_id={session_id}")
        return True

    def add_message(self, session_id: str, message: MessageRecord) -> None:
        """
        向会话追加消息并更新元数据。

        Args:
            session_id: 会话 ID。
            message: 待追加的消息对象。

        Returns:
            None

        Raises:
            TypeError: 当 message 不是 MessageRecord 时抛出。
            ValueError: 当 session_id 不存在时抛出。
        """
        session_id = self._validate_non_empty_str(session_id, "session_id")

        if not isinstance(message, MessageRecord):
            raise TypeError("message 必须是 MessageRecord")

        meta = self.get_session(session_id)
        if not meta:
            raise ValueError(f"session_id 不存在: {session_id}")

        msg_key = f"{SESSION_MSG_PREFIX}{session_id}{SESSION_MSG_SUFFIX}"
        self._client.rpush(msg_key, message.model_dump_json())

        if self.session_ttl > 0:
            self._client.expire(msg_key, self.session_ttl)

        # 更新元数据
        if meta:
            meta.message_count = int(self._client.llen(msg_key))
            meta.updated_at = time.time()
            if meta.name == "新对话" and message.role == "user":
                meta.name = message.content[:15]

            meta_key = f"{SESSION_META_PREFIX}{session_id}{SESSION_META_SUFFIX}"
            self._client.set(meta_key, meta.model_dump_json())
            if self.session_ttl > 0:
                self._client.expire(meta_key, self.session_ttl)

            # 更新用户索引的 score
            user_key = f"{USER_SESSIONS_PREFIX}{meta.user_id}"
            self._client.zadd(user_key, {session_id: meta.updated_at})

    def get_messages(self, session_id: str) -> list[MessageRecord]:
        """
        获取会话的所有消息。

        Args:
            session_id: 会话 ID。

        Returns:
            list[MessageRecord]: 按写入顺序返回的消息列表。
        """
        session_id = self._validate_non_empty_str(session_id, "session_id")

        msg_key = f"{SESSION_MSG_PREFIX}{session_id}{SESSION_MSG_SUFFIX}"
        raw_list: list[str] = list(self._client.lrange(msg_key, 0, -1))
        return [MessageRecord.model_validate_json(raw) for raw in raw_list]

    # ════════════════════════════════════════════════
    #  健康检查
    # ════════════════════════════════════════════════

    def ping(self) -> bool:
        """
        检查 Redis 连接是否正常。

        Args:
            无。

        Returns:
            bool: Redis 可用返回 True，否则返回 False。
        """
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def close(self) -> None:
        """
        关闭 Redis 连接。

        Args:
            无。

        Returns:
            None
        """
        self._client.close()
