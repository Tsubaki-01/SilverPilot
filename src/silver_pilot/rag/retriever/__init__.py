"""
模块名称：retriever
功能描述：RAG 混合检索子包，提供 GraphRAG + 向量多路召回的完整检索流水线。

核心组件：
- QueryProcessor: 查询重写 + 分解 + NER
- EntityLinker: 运行时实体链接
- GraphRetriever: Neo4j 知识图谱检索
- VectorRetriever: Milvus 双集合向量检索
- Reranker: 检索结果重排序
- ContextBuilder: 上下文组装与压缩
- RAGPipeline: 流水线编排器（统一入口）

使用示例::

    from silver_pilot.rag.retriever import RAGPipeline, PipelineConfig

    config = PipelineConfig(reranker_backend="qwen", context_mode="direct")
    pipeline = RAGPipeline(config)
    pipeline.initialize()

    result = pipeline.retrieve("阿司匹林和华法林能一起吃吗")
    print(result.context_text)
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .community_builder import CommunityBuilder
    from .context_builder import ContextBuilder
    from .entity_linker import EntityLinker
    from .graph_models import Community, GraphEdge, GraphNode, ReasoningPath, SubgraphContext
    from .graph_retriever import GraphRetriever
    from .models import (
        ExtractedEntity,
        LinkedEntity,
        ProcessedQuery,
        RetrievalContext,
        RetrievalResult,
        RetrievalSource,
    )
    from .path_reasoner import PathReasoner
    from .pipeline import PipelineConfig, RAGPipeline
    from .query_processor import QueryProcessor
    from .reranker import BaseReranker, BGEReranker, QwenReranker, create_reranker
    from .vector_retriever import VectorRetriever


__all__ = [
    # 流水线
    "RAGPipeline",
    "PipelineConfig",
    # 各阶段组件
    "QueryProcessor",
    "EntityLinker",
    "GraphRetriever",
    "VectorRetriever",
    "ContextBuilder",
    # GraphRAG 专用组件
    "CommunityBuilder",
    "PathReasoner",
    # 重排序
    "BaseReranker",
    "BGEReranker",
    "QwenReranker",
    "create_reranker",
    # 数据模型
    "ProcessedQuery",
    "ExtractedEntity",
    "LinkedEntity",
    "RetrievalResult",
    "RetrievalContext",
    "RetrievalSource",
    # GraphRAG 数据模型
    "GraphNode",
    "GraphEdge",
    "ReasoningPath",
    "Community",
    "SubgraphContext",
]


def __getattr__(name: str) -> Any:
    if name == "CommunityBuilder":
        from .community_builder import CommunityBuilder

        return CommunityBuilder
    if name == "ContextBuilder":
        from .context_builder import ContextBuilder

        return ContextBuilder
    if name == "EntityLinker":
        from .entity_linker import EntityLinker

        return EntityLinker
    if name == "Community":
        from .graph_models import Community

        return Community
    if name == "GraphEdge":
        from .graph_models import GraphEdge

        return GraphEdge
    if name == "GraphNode":
        from .graph_models import GraphNode

        return GraphNode
    if name == "ReasoningPath":
        from .graph_models import ReasoningPath

        return ReasoningPath
    if name == "SubgraphContext":
        from .graph_models import SubgraphContext

        return SubgraphContext
    if name == "GraphRetriever":
        from .graph_retriever import GraphRetriever

        return GraphRetriever
    if name == "ExtractedEntity":
        from .models import ExtractedEntity

        return ExtractedEntity
    if name == "LinkedEntity":
        from .models import LinkedEntity

        return LinkedEntity
    if name == "ProcessedQuery":
        from .models import ProcessedQuery

        return ProcessedQuery
    if name == "RetrievalContext":
        from .models import RetrievalContext

        return RetrievalContext
    if name == "RetrievalResult":
        from .models import RetrievalResult

        return RetrievalResult
    if name == "RetrievalSource":
        from .models import RetrievalSource

        return RetrievalSource
    if name == "PathReasoner":
        from .path_reasoner import PathReasoner

        return PathReasoner
    if name == "PipelineConfig":
        from .pipeline import PipelineConfig

        return PipelineConfig
    if name == "RAGPipeline":
        from .pipeline import RAGPipeline

        return RAGPipeline
    if name == "QueryProcessor":
        from .query_processor import QueryProcessor

        return QueryProcessor
    if name == "BaseReranker":
        from .reranker import BaseReranker

        return BaseReranker
    if name == "BGEReranker":
        from .reranker import BGEReranker

        return BGEReranker
    if name == "QwenReranker":
        from .reranker import QwenReranker

        return QwenReranker
    if name == "create_reranker":
        from .reranker import create_reranker

        return create_reranker
    if name == "VectorRetriever":
        from .vector_retriever import VectorRetriever

        return VectorRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
