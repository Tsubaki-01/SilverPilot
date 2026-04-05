"""
模块名称：schemas
功能描述：Agent 工具模块的 Pydantic Schema 定义。为 Device Agent 的 Function Calling
        提供类型安全的输入参数校验，涵盖提醒设置、设备控制、报警通知、天气查询、
        日历管理等外部工具，以及 RAG 检索、幻觉检测等内部工具。
"""

from enum import StrEnum

from pydantic import BaseModel, Field

# ────────────────────────────────────────────────────────────
# 风险等级枚举
# ────────────────────────────────────────────────────────────


class RiskLevel(StrEnum):
    """工具操作的风险等级，决定是否需要用户确认。"""

    LOW = "low"
    """低风险：查询天气、设置普通提醒等，直接执行。"""

    MEDIUM = "medium"
    """中风险：修改用药提醒、调整家居参数，需要确认后执行。"""

    HIGH = "high"
    """高风险：删除所有提醒、拨打急救电话等，需要 HITL 中断 + 双重确认。"""


# ────────────────────────────────────────────────────────────
# 外部工具 Schema
# ────────────────────────────────────────────────────────────

# TODO 计算器


class SetReminderInput(BaseModel):
    """设置提醒工具的输入参数。"""

    time: str = Field(description="提醒时间，ISO 8601 格式，如 '2024-01-15T07:00:00'")
    message: str = Field(description="提醒内容，如 '该吃降压药了'")
    repeat: str = Field(
        default="none",
        description="重复规则：none（不重复）、daily（每天）、weekly（每周）",
    )
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="操作风险等级")


class DeviceControlInput(BaseModel):
    """智能家居设备控制工具的输入参数。"""

    device_id: str = Field(description="设备唯一标识，如 'living_room_ac'")
    action: str = Field(description="控制动作：on / off / set / adjust")
    value: str = Field(default="", description="设置值，如温度 '26'、亮度 '80'")
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM, description="操作风险等级")


class SendAlertInput(BaseModel):
    """发送报警通知工具的输入参数。"""

    # TODO: EMail
    contact: str = Field(description="联系人姓名或电话号码")
    message: str = Field(description="报警内容")
    urgency: str = Field(
        default="normal",
        description="紧急程度：normal（普通）、urgent（紧急）、critical（危急）",
    )
    risk_level: RiskLevel = Field(default=RiskLevel.HIGH, description="操作风险等级")


class WeatherQueryInput(BaseModel):
    """天气查询工具的输入参数。"""

    location: str = Field(description="查询地点，如 '上海'、'北京海淀区'")
    date: str = Field(
        default="today",
        description="查询日期：today / tomorrow / 具体日期",
    )
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="操作风险等级")


class WeatherForecastInput(BaseModel):
    """多日天气预报工具的输入参数（由 MCP Server 执行）。"""

    location: str = Field(description="查询城市，如 '广州'、'成都'")
    days: int = Field(default=3, description="预报天数，范围 1-7")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="操作风险等级")


class CalendarEventInput(BaseModel):
    """日历事件工具的输入参数。"""

    title: str = Field(description="事件标题，如 '去医院复查'")
    start: str = Field(description="开始时间，ISO 8601 格式")
    end: str = Field(default="", description="结束时间，ISO 8601 格式")
    remind_before: int = Field(default=30, description="提前提醒时间（分钟）")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="操作风险等级")


# ────────────────────────────────────────────────────────────
# 工具注册表
# ────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, type[BaseModel]] = {
    "set_reminder": SetReminderInput,
    "control_device": DeviceControlInput,
    "send_alert": SendAlertInput,
    "query_weather": WeatherQueryInput,
    "weather_forecast": WeatherForecastInput,
    "set_calendar": CalendarEventInput,
}
"""工具名称到输入 Schema 的映射表，供 Device Agent 解析和校验使用。"""
