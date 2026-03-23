from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .database.milvus_manager import MilvusManager
    from .database.neo4j_manager import Neo4jManager


__all__: list[str] = [
    "MilvusManager",
    "Neo4jManager",
]


def __getattr__(name: str) -> Any:
    if name == "MilvusManager":
        from .database.milvus_manager import MilvusManager

        return MilvusManager
    if name == "Neo4jManager":
        from .database.neo4j_manager import Neo4jManager

        return Neo4jManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
