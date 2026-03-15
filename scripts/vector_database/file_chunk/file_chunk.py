from silver_pilot.config import config
from silver_pilot.rag.chunker import UnifiedChunker

source_path = config.DATA_DIR / "processed" / "extract" / "milvus"
output_dir = config.DATA_DIR / "processed" / "extract" / "milvus" / "chunks"

chunker = UnifiedChunker()
chunker.process(
    source_path=source_path,
    output_dir=output_dir,
)
