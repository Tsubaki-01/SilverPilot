"""Agent 节点子包。"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .chat_agent import chat_agent_node
    from .device_agent import device_agent_node
    from .emergency_agent import emergency_agent_node
    from .medical_agent import medical_agent_node
    from .memory_writer import memory_writer_node
    from .output_guard import output_guard_node
    from .perception_router import perception_router_node
    from .response_synthesizer import response_synthesizer_node
    from .supervisor import route_by_intent, supervisor_node


__all__ = [
    "perception_router_node",
    "supervisor_node",
    "route_by_intent",
    "medical_agent_node",
    "device_agent_node",
    "chat_agent_node",
    "emergency_agent_node",
    "response_synthesizer_node",
    "output_guard_node",
    "memory_writer_node",
]


def __getattr__(name: str) -> Any:
    if name == "chat_agent_node":
        from .chat_agent import chat_agent_node

        return chat_agent_node
    if name == "device_agent_node":
        from .device_agent import device_agent_node

        return device_agent_node
    if name == "emergency_agent_node":
        from .emergency_agent import emergency_agent_node

        return emergency_agent_node
    if name == "medical_agent_node":
        from .medical_agent import medical_agent_node

        return medical_agent_node
    if name == "memory_writer_node":
        from .memory_writer import memory_writer_node

        return memory_writer_node
    if name == "output_guard_node":
        from .output_guard import output_guard_node

        return output_guard_node
    if name == "perception_router_node":
        from .perception_router import perception_router_node

        return perception_router_node
    if name == "response_synthesizer_node":
        from .response_synthesizer import response_synthesizer_node

        return response_synthesizer_node
    if name == "route_by_intent":
        from .supervisor import route_by_intent

        return route_by_intent
    if name == "supervisor_node":
        from .supervisor import supervisor_node

        return supervisor_node
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
