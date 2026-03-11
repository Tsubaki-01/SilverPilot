"""
模块名称：chunker
功能描述：RAG 切片子包，提供 Excel 和 Markdown 两种文档切片能力。
         共享 DocumentChunk 数据结构，支持统一入库。
"""

from .chunker_base import DocumentChunk, TextSplitter
from .excel_chunker import DRUG_INSTRUCTION_GROUPS, ChunkGroup, ExcelChunker
from .markdown_chunker import MarkdownChunker

__all__ = [
    # 共享数据结构
    "DocumentChunk",
    "TextSplitter",
    # Excel 切片
    "ExcelChunker",
    "ChunkGroup",
    "DRUG_INSTRUCTION_GROUPS",
    # Markdown 切片
    "MarkdownChunker",
]
