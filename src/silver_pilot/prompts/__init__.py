"""
模块名称：prompts
功能描述：Prompt 管理子包的初始化模块，对外暴露 prompt_manager 单例实例，
         用于统一管理和渲染 YAML 格式的 Prompt 模板。
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .prompt_manager import prompt_manager


__all__ = ["prompt_manager"]


def __getattr__(name: str) -> Any:
    if name == "prompt_manager":
        from .prompt_manager import prompt_manager

        return prompt_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
