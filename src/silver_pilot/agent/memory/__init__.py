"""
模块名称：memory
功能描述：Agent 记忆子包，提供短期对话摘要压缩和长期用户画像持久化能力。
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .summarizer import ConversationSummarizer
    from .user_profile import UserProfileManager


__all__ = [
    "ConversationSummarizer",
    "UserProfileManager",
]


def __getattr__(name: str) -> Any:
    if name == "ConversationSummarizer":
        from .summarizer import ConversationSummarizer

        return ConversationSummarizer
    if name == "UserProfileManager":
        from .user_profile import UserProfileManager

        return UserProfileManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
