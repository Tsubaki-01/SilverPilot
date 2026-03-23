"""
模块名称：agent
功能描述：Silver Pilot Agent 系统核心包。

架构概览：
    - 感知层（Perception）：多模态输入标准化（文本/语音/图像）
    - 认知层（Cognitive）：Supervisor 意图分类 + 子 Agent 路由
    - 记忆层（Memory）：短期对话摘要 + 长期用户画像
    - 行动层（Action）：工具执行引擎 + 安全校验

核心组件：
    - AgentState: 全局共享状态定义
    - build_agent_graph: LangGraph 图拓扑构建器
    - Nodes: 各阶段节点实现
    - Tools: 工具 Schema 与执行引擎
    - Memory: 摘要压缩 + 画像持久化


推荐使用方式::

    from silver_pilot.agent import initialize_agent, create_initial_state
    from langchain_core.messages import HumanMessage

    # 系统启动（一次性，完成所有组件初始化）
    graph = initialize_agent()

    # 运行时调用
    state = create_initial_state()
    state["messages"] = [HumanMessage(content="阿司匹林一天吃几次")]
    result = graph.invoke(state, config={"configurable": {"thread_id": "s1"}})
    print(result["final_response"])
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .bootstrap import initialize_agent
    from .graph import build_agent_graph
    from .state import AgentState, create_initial_state


__all__ = [
    "initialize_agent",
    "build_agent_graph",
    "AgentState",
    "create_initial_state",
]


def __getattr__(name: str) -> Any:
    if name == "initialize_agent":
        from .bootstrap import initialize_agent

        return initialize_agent
    if name == "build_agent_graph":
        from .graph import build_agent_graph

        return build_agent_graph
    if name == "AgentState":
        from .state import AgentState

        return AgentState
    if name == "create_initial_state":
        from .state import create_initial_state

        return create_initial_state
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
