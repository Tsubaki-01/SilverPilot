from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .pipeline_base import BaseDocumentPipeline


__all__ = ["BaseDocumentPipeline"]


def __getattr__(name: str) -> Any:
    if name == "BaseDocumentPipeline":
        from .pipeline_base import BaseDocumentPipeline

        return BaseDocumentPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
