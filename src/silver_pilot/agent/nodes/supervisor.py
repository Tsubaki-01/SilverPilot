"""
模块名称：supervisor
功能描述：Supervisor 循环编排节点，Agent 系统的"大脑"。负责意图分类、复合意图拆解、
         子 Agent 路由调度，以及循环终止判断。通过 LLM 结构化输出实现意图解析，
         按优先级顺序逐一分发给子 Agent 执行。

核心职责：
    1. 调用 LLM 对用户输入进行意图分类（支持复合意图拆解）
    2. 按优先级排序意图队列，逐一路由到对应子 Agent
    3. 子 Agent 执行完毕后检查队列是否清空
    4. 执行循环终止保护（最大循环次数、超时）
"""

from pathlib import Path

from langgraph.types import Send
from pydantic import BaseModel, Field

from silver_pilot.config import config
from silver_pilot.prompts import prompt_manager
from silver_pilot.utils import get_channel_logger

from ..llm import call_llm_parse
from ..state import MAX_SUPERVISOR_LOOPS, AgentState
from .helpers import build_profile_summary, extract_latest_query, get_conversation_context

# ================= 日志 =================
LOG_FILE_DIR: Path = config.LOG_DIR / "agent"
logger = get_channel_logger(LOG_FILE_DIR, "supervisor")

# ================= 默认配置 =================
SUPERVISOR_LLM_MODEL: str = config.SUPERVISOR_MODEL
PROMPT_TEMPLATE: str = "agent/supervisor_classify"


# ── 意图类型 → 节点名映射 ──
INTENT_TO_AGENT: dict[str, str] = {
    "EMERGENCY": "emergency",
    "MEDICAL_QUERY": "medical",
    "DEVICE_CONTROL": "device",
    "CHITCHAT": "chat",
}

# ── 降级默认返回值 ──
_FALLBACK_STATE: dict = {
    "pending_intents": [],
    "current_agent": "chat",
    "risk_level": "low",
    "loop_count": 1,
    "retry_count": 0,
}

# ────────────────────────────────────────────────────────────
# Pydantic 结构化输出 Schema
# ────────────────────────────────────────────────────────────


class IntentItem(BaseModel):
    """单个意图的结构化表示。"""

    type: str = Field(description="意图类型: EMERGENCY / MEDICAL_QUERY / DEVICE_CONTROL / CHITCHAT")
    sub_query: str = Field(description="该意图对应的具体子查询")
    priority: int = Field(description="优先级数值，越小越高")


class SupervisorOutput(BaseModel):
    """Supervisor LLM 的结构化输出。"""

    intents: list[IntentItem] = Field(description="识别到的意图列表")
    risk_level: str = Field(default="low", description="整体风险等级")


# ────────────────────────────────────────────────────────────
# Supervisor 节点
# ────────────────────────────────────────────────────────────


def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 编排节点：一次意图分类 + 一次路由决策。

    执行逻辑：
        1. 首次进入调用 LLM 分类并保存意图列表
        2. EMERGENCY 短路：仅路由到 emergency
        3. 单意图：路由到对应单个子 Agent
        4. 多意图：标记 current_agent="parallel"，由 route_by_intent 返回 Send 并行分发

    Args:
        state: 当前 AgentState

    Returns:
        dict: 包含 pending_intents、current_agent、risk_level、loop_count 的状态更新
    """
    loop_count = state.get("loop_count", 0)

    # ── 循环保护 ──
    if loop_count >= MAX_SUPERVISOR_LOOPS:
        logger.warning(f"达到最大循环次数 {MAX_SUPERVISOR_LOOPS}，强制终止")
        return {
            "current_agent": "done",
        }

    # 新架构中 Supervisor 每轮仅执行一次分类和路由
    return _classify_and_dispatch(state)


# ────────────────────────────────────────────────────────────
# 辅助函数
# ────────────────────────────────────────────────────────────


def _classify_and_dispatch(state: AgentState) -> dict:
    """调用 LLM 分类意图并生成一次性分发策略。"""
    user_query = extract_latest_query(state)
    if not user_query:
        logger.warning("无法提取用户查询，降级为闲聊")
        return {**_FALLBACK_STATE}

    logger.info(f"意图分类开始 | user_query={user_query}")
    # 构建 Prompt 并调用 LLM
    messages = prompt_manager.build_prompt(
        PROMPT_TEMPLATE,
        user_query=user_query,
        current_audio_context=state.get("current_audio_context", ""),
        user_emotion=state.get("user_emotion", "NEUTRAL"),
        current_image_context=state.get("current_image_context", ""),
        conversation_summary=get_conversation_context(state.get("messages", [])),
        user_profile_summary=build_profile_summary(state.get("user_profile", {})),
    )

    parsed = call_llm_parse(SUPERVISOR_LLM_MODEL, messages, SupervisorOutput)
    if parsed is None or not parsed.intents:
        logger.warning("意图分类失败或为空，降级为闲聊")
        return {**_FALLBACK_STATE}

    # 按优先级排序
    sorted_intents = sorted(
        [intent.model_dump() for intent in parsed.intents],
        key=lambda x: x["priority"],
    )

    # Emergency 短路：仅处理紧急意图
    emergency_intent = next((i for i in sorted_intents if i.get("type") == "EMERGENCY"), None)
    if emergency_intent:
        logger.warning("检测到 EMERGENCY，短路到 emergency_agent")
        return {
            "pending_intents": [emergency_intent],
            "current_agent": "emergency",
            "current_sub_query": emergency_intent.get("sub_query", user_query),
            "risk_level": "critical",
            "loop_count": 1,
            "retry_count": 0,
            "total_turns": state.get("total_turns", 0) + 1,
        }

    if len(sorted_intents) == 1:
        only = sorted_intents[0]
        only_agent = INTENT_TO_AGENT.get(only["type"], "chat")
        logger.info(f"单意图路由 | type={only['type']} | agent={only_agent}")
        return {
            "pending_intents": sorted_intents,
            "current_agent": only_agent,
            "current_sub_query": only.get("sub_query", ""),
            "risk_level": parsed.risk_level,
            "loop_count": 1,
            "retry_count": 0,
            "total_turns": state.get("total_turns", 0) + 1,
        }

    logger.info(f"多意图并行路由 | count={len(sorted_intents)}")
    logger.info(
        f"意图分类完成 | types={[i['type'] for i in sorted_intents]} | risk={parsed.risk_level}"
    )

    return {
        "pending_intents": sorted_intents,
        "current_agent": "parallel",
        "current_sub_query": "",
        "risk_level": parsed.risk_level,
        "loop_count": 1,
        "retry_count": 0,
        "total_turns": state.get("total_turns", 0) + 1,
    }


# ────────────────────────────────────────────────────────────
# 路由函数（供 LangGraph conditional_edges 使用）
# ────────────────────────────────────────────────────────────


def route_by_intent(state: AgentState) -> str | list[Send]:
    """
    条件路由函数：根据 current_agent 决定下一个执行节点。

    Args:
        state: 当前 AgentState

    Returns:
        str | list[Send]: 单意图返回节点名；多意图返回 Send 列表并行分发
    """
    agent = state.get("current_agent", "done")
    if agent == "parallel":
        # 同类型意图合并为一次分发，避免并行写冲突。
        grouped_queries: dict[str, list[str]] = {
            "medical": [],
            "device": [],
            "chat": [],
        }
        for intent in state.get("pending_intents", []):
            agent_key = INTENT_TO_AGENT.get(intent.get("type", "CHITCHAT"), "chat")
            if agent_key == "emergency":
                # emergency 已在 supervisor_node 中短路处理，这里忽略
                continue
            grouped_queries.setdefault(agent_key, [])
            grouped_queries[agent_key].append(intent.get("sub_query", ""))

        sends: list[Send] = []
        active_branches: list[str] = []
        for agent_key, queries in grouped_queries.items():
            if not queries:
                continue
            merged_query = "；".join(q for q in queries if q)
            active_branches.append(agent_key)
            sends.append(
                Send(
                    f"{agent_key}_agent",
                    {
                        "current_sub_query": merged_query,
                    },
                )
            )

        logger.info(f"并行分发 | branches={active_branches}")
        return sends if sends else "chat"

    logger.debug(f"路由决策 | current_agent={agent}")
    return agent
