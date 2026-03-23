from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .cleaner import MarkdownCleaner
    from .converter import MinerUConverter
    from .markdown_convert_pipeline import MarkdownConverter
    from .parser import ExcelParser, ExcelPasedRow


__all__ = [
    "ExcelParser",
    "ExcelPasedRow",
    "MarkdownCleaner",
    "MinerUConverter",
    "MarkdownConverter",
]


def __getattr__(name: str) -> Any:
    if name == "MarkdownCleaner":
        from .cleaner import MarkdownCleaner

        return MarkdownCleaner
    if name == "MinerUConverter":
        from .converter import MinerUConverter

        return MinerUConverter
    if name == "MarkdownConverter":
        from .markdown_convert_pipeline import MarkdownConverter

        return MarkdownConverter
    if name == "ExcelParser":
        from .parser import ExcelParser

        return ExcelParser
    if name == "ExcelPasedRow":
        from .parser import ExcelPasedRow

        return ExcelPasedRow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
