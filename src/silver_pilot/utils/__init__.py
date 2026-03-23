"""
模块名称：utils
功能描述：项目需要的轮子模块，如日志、文件操作等
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .log import get_channel_logger


__all__ = ["get_channel_logger"]


def __getattr__(name: str) -> Any:
    if name == "get_channel_logger":
        from .log import get_channel_logger

        return get_channel_logger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
