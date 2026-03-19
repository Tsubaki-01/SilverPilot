"""
模块名称：executor
功能描述：工具执行引擎，负责接收结构化的工具调用请求，进行风险评级校验后执行工具，
        并将执行结果格式化返回。支持低风险直接执行、中风险确认执行、高风险 HITL 中断。
"""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from silver_pilot.config import config
from silver_pilot.utils import get_channel_logger

from .schemas import TOOL_REGISTRY, RiskLevel

# ================= 日志 =================
LOG_FILE_DIR: Path = config.LOG_DIR / "agent"
logger = get_channel_logger(LOG_FILE_DIR, "tool_executor")
# ========================================


class ToolExecutionResult:
    """
    工具执行结果的标准化封装。

    Attributes:
        tool_name: 工具名称
        success: 是否执行成功
        result: 执行返回的数据
        error: 错误信息（失败时）
        needs_confirmation: 是否需要用户确认（中/高风险操作）
        risk_level: 工具操作的风险等级
    """

    __slots__ = ("tool_name", "success", "result", "error", "needs_confirmation", "risk_level")

    def __init__(
        self,
        tool_name: str,
        success: bool = True,
        result: Any = None,
        error: str = "",
        needs_confirmation: bool = False,
        risk_level: str = "low",
    ) -> None:
        self.tool_name = tool_name
        self.success = success
        self.result = result
        self.error = error
        self.needs_confirmation = needs_confirmation
        self.risk_level = risk_level

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，便于写入 AgentState.tool_results。"""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "needs_confirmation": self.needs_confirmation,
            "risk_level": self.risk_level,
        }


class ToolExecutor:
    """
    统一的工具执行引擎。

    职责：
        1. 校验工具名称和参数（基于 Pydantic Schema）
        2. 评估操作风险等级
        3. 低风险直接执行，中/高风险返回确认请求
        4. 执行工具并格式化返回结果

    使用示例::

        executor = ToolExecutor()
        result = executor.execute("set_reminder", {
            "time": "2024-01-15T07:00:00",
            "message": "该吃降压药了",
            "repeat": "daily",
        })
        print(result.to_dict())
    """

    # ================= 类级常量 (策略配置) =================
    _DEFAULT_TOOL_RISKS: dict[str, RiskLevel] = {
        "query_weather": RiskLevel.LOW,
        "set_reminder": RiskLevel.LOW,
        "set_calendar": RiskLevel.LOW,
        "control_device": RiskLevel.MEDIUM,
        "send_alert": RiskLevel.HIGH,
    }

    _CONFIRMATION_TEMPLATES: dict[str, str] = {
        "control_device": (
            "{risk_label}操作确认：即将对设备 {device_id} 执行 {action} 操作，确认执行吗？"
        ),
        "send_alert": (
            "{risk_label}操作确认：即将向 {contact} 发送紧急通知「{message}」，确认发送吗？"
        ),
        "default": "{risk_label}操作确认：即将执行 {tool_name}，确认继续吗？",
    }

    _SIMULATED_SUCCESS_TEMPLATES: dict[str, str] = {
        "set_reminder": "已设置提醒: {message}，时间: {time}",
        "control_device": "设备 {device_id} 已执行 {action}",
        "send_alert": "已向 {contact} 发送通知",
        "set_calendar": "已创建日历事件: {title}，时间: {start}",
    }
    # ======================================================

    def __init__(self) -> None:
        logger.info("ToolExecutor 初始化完成")

    def validate_and_parse(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[Any | None, str]:
        """
        校验工具名称和参数。

        Args:
            tool_name: 工具名称
            arguments: 工具参数字典

        Returns:
            tuple: (解析后的 Pydantic 对象, 错误信息)。成功时错误信息为空字符串。
        """
        schema_cls = TOOL_REGISTRY.get(tool_name)
        if schema_cls is None:
            return None, f"未知工具: {tool_name}，可用工具: {list(TOOL_REGISTRY.keys())}"

        try:
            parsed = schema_cls(**arguments)
            return parsed, ""
        except ValidationError as e:
            return None, f"参数校验失败: {e}"

    def evaluate_risk(self, tool_name: str, parsed_input: Any) -> RiskLevel:
        """
        评估工具操作的风险等级。

        优先使用工具 Schema 中声明的 risk_level，其次根据工具名称使用默认评级。

        Args:
            tool_name: 工具名称
            parsed_input: 解析后的 Pydantic 输入对象

        Returns:
            RiskLevel: 评估后的风险等级
        """
        # 优先读取 Schema 中声明的风险等级
        if hasattr(parsed_input, "risk_level"):
            return RiskLevel(parsed_input.risk_level)

        # 兜底：根据工具名称使用默认评级
        return self._DEFAULT_TOOL_RISKS.get(tool_name, RiskLevel.MEDIUM)

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        user_confirmed: bool = False,
    ) -> ToolExecutionResult:
        """
        执行工具调用的完整流程：校验 → 风险评估 → 执行/确认。

        Args:
            tool_name: 工具名称
            arguments: 工具参数字典
            user_confirmed: 用户是否已确认（用于中/高风险操作的二次调用）

        Returns:
            ToolExecutionResult: 执行结果
        """
        logger.info(f"工具调用请求 | tool={tool_name} | args={arguments}")

        # 1. 校验参数
        parsed, error = self.validate_and_parse(tool_name, arguments)
        if error:
            logger.warning(f"工具参数校验失败 | tool={tool_name} | error={error}")
            return ToolExecutionResult(tool_name=tool_name, success=False, error=error)

        # 2. 风险评估
        risk = self.evaluate_risk(tool_name, parsed)
        logger.info(f"风险评估 | tool={tool_name} | risk={risk.value}")

        # 3. 高风险且未确认 → 返回确认请求
        if risk in (RiskLevel.MEDIUM, RiskLevel.HIGH) and not user_confirmed:
            confirm_msg = self._build_confirmation_message(tool_name, parsed, risk)
            logger.info(f"需要用户确认 | tool={tool_name} | risk={risk.value}")
            return ToolExecutionResult(
                tool_name=tool_name,
                success=True,
                result={"confirmation_message": confirm_msg},
                needs_confirmation=True,
                risk_level=risk.value,
            )

        # 4. 执行工具
        return self._execute_tool(tool_name, parsed, risk)

    def _execute_tool(
        self,
        tool_name: str,
        parsed_input: Any,
        risk: RiskLevel,
    ) -> ToolExecutionResult:
        """
        执行具体的工具逻辑。

        当前阶段使用模拟实现，后续接入真实 API。
        每个工具返回结构化的执行结果。
        """
        try:
            # ── 模拟执行（后续替换为真实 API 调用）──
            result = self._simulate_tool_execution(tool_name, parsed_input)

            logger.info(f"工具执行成功 | tool={tool_name} | result={result}")
            return ToolExecutionResult(
                tool_name=tool_name,
                success=True,
                result=result,
                risk_level=risk.value,
            )

        except Exception as e:
            logger.error(f"工具执行失败 | tool={tool_name} | error={e}")
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                risk_level=risk.value,
            )

    @staticmethod
    def _build_confirmation_message(
        tool_name: str,
        parsed_input: Any,
        risk: RiskLevel,
    ) -> str:
        """为中/高风险操作构建用户确认提示语。"""
        risk_label = "⚠️ 中风险" if risk == RiskLevel.MEDIUM else "🚨 高风险"

        template = ToolExecutor._CONFIRMATION_TEMPLATES.get(
            tool_name, ToolExecutor._CONFIRMATION_TEMPLATES["default"]
        )

        return template.format(
            risk_label=risk_label,
            tool_name=tool_name,
            **parsed_input.model_dump(),
        )

    # TODO 目前是模拟实现，后续替换为真实 API 调用
    @staticmethod
    def _simulate_tool_execution(tool_name: str, parsed_input: Any) -> dict[str, Any]:
        """
        模拟工具执行（开发阶段）。

        后续每个工具将替换为真实的 API 调用：
        - set_reminder → 日历服务 API
        - control_device → 智能家居网关 API
        - send_alert → 短信/电话 API
        - query_weather → 天气服务 API
        - set_calendar → 日历服务 API
        """
        if tool_name == "query_weather":
            return {
                "status": "success",
                "weather": "晴转多云",
                "temperature": "18-25°C",
                "location": parsed_input.location,
            }

        if tool_name in ToolExecutor._SIMULATED_SUCCESS_TEMPLATES:
            status = "created" if tool_name.startswith("set_") else "executed"
            if tool_name == "send_alert":
                status = "sent"

            template = ToolExecutor._SIMULATED_SUCCESS_TEMPLATES[tool_name]
            # 这里统一使用 model_dump() 提取参数进行格式化
            return {
                "status": status,
                "message": template.format(**parsed_input.model_dump()),
            }

        return {"status": "unknown_tool"}
