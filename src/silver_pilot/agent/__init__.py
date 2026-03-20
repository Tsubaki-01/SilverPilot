"""
模块名称：agent
功能描述：Silver Pilot Agent 系统核心包，基于 LangGraph 实现 Supervisor 多智能体编排。

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

使用示例::

    from silver_pilot.agent import build_agent_graph, create_initial_state

    # 构建图
    graph = build_agent_graph()

    # 执行查询
    initial_state = create_initial_state()
    initial_state["messages"] = [HumanMessage(content="阿司匹林一天吃几次")]
    result = graph.invoke(initial_state, config={"configurable": {"thread_id": "session_001"}})
    print(result["final_response"])
"""

from .graph import build_agent_graph, build_default_graph
from .state import (
    AgentState,
    create_initial_state,
)

__all__ = [
    # 核心 API
    "build_agent_graph",
    "build_default_graph",
    "AgentState",
    "create_initial_state",
]
