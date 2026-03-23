"""
模块名称：tools
功能描述：Agent 工具子包，提供工具 Schema 定义和统一执行引擎。
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .executor import ToolExecutionResult, ToolExecutor
    from .schemas import (
        TOOL_REGISTRY,
        CalendarEventInput,
        DeviceControlInput,
        RiskLevel,
        SendAlertInput,
        SetReminderInput,
        WeatherQueryInput,
    )


__all__ = [
    "ToolExecutor",
    "ToolExecutionResult",
    "RiskLevel",
    "TOOL_REGISTRY",
    "SetReminderInput",
    "DeviceControlInput",
    "SendAlertInput",
    "WeatherQueryInput",
    "CalendarEventInput",
]


def __getattr__(name: str) -> Any:
    if name == "ToolExecutionResult":
        from .executor import ToolExecutionResult

        return ToolExecutionResult
    if name == "ToolExecutor":
        from .executor import ToolExecutor

        return ToolExecutor
    if name == "TOOL_REGISTRY":
        from .schemas import TOOL_REGISTRY

        return TOOL_REGISTRY
    if name == "CalendarEventInput":
        from .schemas import CalendarEventInput

        return CalendarEventInput
    if name == "DeviceControlInput":
        from .schemas import DeviceControlInput

        return DeviceControlInput
    if name == "RiskLevel":
        from .schemas import RiskLevel

        return RiskLevel
    if name == "SendAlertInput":
        from .schemas import SendAlertInput

        return SendAlertInput
    if name == "SetReminderInput":
        from .schemas import SetReminderInput

        return SetReminderInput
    if name == "WeatherQueryInput":
        from .schemas import WeatherQueryInput

        return WeatherQueryInput
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
