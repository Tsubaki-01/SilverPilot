from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .excel_parser import DRUG_CONFIG, ExcelParser, ExcelPasedRow


__all__ = ["ExcelParser", "ExcelPasedRow", "DRUG_CONFIG"]


def __getattr__(name: str) -> Any:
    if name == "DRUG_CONFIG":
        from .excel_parser import DRUG_CONFIG

        return DRUG_CONFIG
    if name == "ExcelParser":
        from .excel_parser import ExcelParser

        return ExcelParser
    if name == "ExcelPasedRow":
        from .excel_parser import ExcelPasedRow

        return ExcelPasedRow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
