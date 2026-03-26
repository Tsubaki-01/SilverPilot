"""
模块名称：user_profile
功能描述：长期用户画像管理器。SQLite 后端实现 + Protocol 接口定义。
         RedisStore 实现了相同的 Protocol，可直接替换注入。

设计说明：
    - UserProfileManager 保持原有类名和接口不变（SQLite 后端）
    - ProfileManagerProtocol 定义鸭子类型接口
    - bootstrap.py 注入时可传入 RedisStore 实例（符合 Protocol）
    - 开发阶段使用 SQLite（零依赖），生产阶段可切换 Redis
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from silver_pilot.config import config
from silver_pilot.utils import get_channel_logger

# ================= 日志 =================
LOG_FILE_DIR: Path = config.LOG_DIR / "agent"
logger = get_channel_logger(LOG_FILE_DIR, "user_profile")

# ================= 默认配置 =================
DEFAULT_DB_PATH: Path = config.DATA_DIR / "agent" / "user_profiles.db"


# ────────────────────────────────────────────────────────────
# 协议定义（鸭子类型接口）
# ────────────────────────────────────────────────────────────


@runtime_checkable
class ProfileManagerProtocol(Protocol):
    """
    用户画像管理器的接口协议。

    UserProfileManager (SQLite) 和 RedisStore 均实现此协议，
    可在 bootstrap 和 memory_writer 中互相替换。
    """

    def get_profile(self, user_id: str) -> dict[str, Any]: ...
    def update_profile(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...
    def delete_profile(self, user_id: str) -> bool: ...


# ────────────────────────────────────────────────────────────
# 默认用户画像模板
# ────────────────────────────────────────────────────────────

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


# ────────────────────────────────────────────────────────────
# UserProfileManager（SQLite 后端，保持原有类名）
# ────────────────────────────────────────────────────────────


class UserProfileManager:
    """
    长期用户画像管理器（SQLite 后端）。

    提供用户画像的 CRUD 操作，数据以 JSON 格式序列化存储在 SQLite 中。
    支持增量更新，仅修改变更的字段。

    使用示例::

        manager = UserProfileManager()
        profile = manager.get_profile("elderly_001")
        manager.update_profile("elderly_001", {
            "chronic_diseases": ["高血压", "糖尿病"],
        })

    替换方案：
        生产环境可使用 RedisStore（实现了相同的 ProfileManagerProtocol），
        通过 bootstrap.py 的 profile_manager 参数注入。
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"UserProfileManager 初始化完成 | db={self.db_path}")

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id     TEXT PRIMARY KEY,
                    profile     TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
            """)
            conn.commit()

    def get_profile(self, user_id: str) -> dict[str, Any]:
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT profile FROM user_profiles WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

        if row:
            profile = json.loads(row[0])
            logger.debug(f"加载用户画像 | user_id={user_id}")
            return profile

        logger.info(f"用户不存在，创建默认画像 | user_id={user_id}")
        return self._create_default_profile(user_id)

    def update_profile(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
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
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "DELETE FROM user_profiles WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"用户画像已删除 | user_id={user_id}")
        else:
            logger.warning(f"用户画像不存在，删除无效 | user_id={user_id}")
        return deleted

    def _create_default_profile(self, user_id: str) -> dict[str, Any]:
        """创建默认用户画像并保存到数据库。"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        profile = {**DEFAULT_PROFILE, "user_id": user_id, "created_at": now, "updated_at": now}
        self._save_profile(user_id, profile)
        return profile

    def _save_profile(self, user_id: str, profile: dict[str, Any]) -> None:
        """将画像序列化后写入 SQLite。"""
        profile_json = json.dumps(profile, ensure_ascii=False)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (user_id, profile, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET profile = excluded.profile, updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    profile_json,
                    profile.get("created_at", ""),
                    profile.get("updated_at", ""),
                ),
            )
            conn.commit()
