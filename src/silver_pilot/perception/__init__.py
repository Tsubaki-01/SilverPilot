"""
模块名称：perception
功能描述：Silver Pilot 多模态感知子包，提供文本向量化、语音识别和视觉理解能力。

核心组件：
    - Embedder: 文本向量化（Qwen API / 本地 BGE-M3）
    - AudioProcessor: 语音转文字 + 情感识别（ASR API）
    - VisionProcessor: 图像理解 + OCR 提取（Qwen API）
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .audio import AudioProcessor, AudioResult
    from .embedder import BaseEmbedder, create_embedder
    from .vision import VisionProcessor


__all__ = [
    # Embedder
    "create_embedder",
    "BaseEmbedder",
    # Audio
    "AudioProcessor",
    "AudioResult",
    # Vision
    "VisionProcessor",
]


def __getattr__(name: str) -> Any:
    if name == "AudioProcessor":
        from .audio import AudioProcessor

        return AudioProcessor
    if name == "AudioResult":
        from .audio import AudioResult

        return AudioResult
    if name == "BaseEmbedder":
        from .embedder import BaseEmbedder

        return BaseEmbedder
    if name == "create_embedder":
        from .embedder import create_embedder

        return create_embedder
    if name == "VisionProcessor":
        from .vision import VisionProcessor

        return VisionProcessor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
