"""
模块名称：chunker
功能描述：RAG 切片子包，提供 Excel 和 Markdown 两种文档切片能力。
         共享 DocumentChunk 数据结构，支持统一入库。
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .unified_chunker import UnifiedChunker


__all__ = ["UnifiedChunker"]


def __getattr__(name: str) -> Any:
    if name == "UnifiedChunker":
        from .unified_chunker import UnifiedChunker

        return UnifiedChunker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
