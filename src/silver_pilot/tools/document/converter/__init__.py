from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .mineru_converter import MinerUConverter


__all__ = ["MinerUConverter"]


def __getattr__(name: str) -> Any:
    if name == "MinerUConverter":
        from .mineru_converter import MinerUConverter

        return MinerUConverter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
