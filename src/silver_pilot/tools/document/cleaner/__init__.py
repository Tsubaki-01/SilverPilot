from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .md_cleaner import CleanOptions, MarkdownCleaner


__all__ = ["MarkdownCleaner", "CleanOptions"]


def __getattr__(name: str) -> Any:
    if name == "CleanOptions":
        from .md_cleaner import CleanOptions

        return CleanOptions
    if name == "MarkdownCleaner":
        from .md_cleaner import MarkdownCleaner

        return MarkdownCleaner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
