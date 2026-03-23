"""
模块名称：rag
功能描述：RAG 知识库构建与检索模块，涵盖文档解析、分块、入库以及混合检索流水线。
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import chunker, retriever
    from .ingestor import ChunkIngestor
    from .retriever import PipelineConfig, RAGPipeline, RetrievalContext


__all__ = [
    "chunker",
    "retriever",
    "ChunkIngestor",
    "RAGPipeline",
    "PipelineConfig",
    "RetrievalContext",
]


def __getattr__(name: str) -> Any:
    if name == "chunker":
        from . import chunker

        return chunker
    if name == "retriever":
        from . import retriever

        return retriever
    if name == "ChunkIngestor":
        from .ingestor import ChunkIngestor

        return ChunkIngestor
    if name == "PipelineConfig":
        from .retriever import PipelineConfig

        return PipelineConfig
    if name == "RAGPipeline":
        from .retriever import RAGPipeline

        return RAGPipeline
    if name == "RetrievalContext":
        from .retriever import RetrievalContext

        return RetrievalContext
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
