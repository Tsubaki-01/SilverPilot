from silver_pilot.config import config
from silver_pilot.rag import ChunkIngestor

JSON_DIR = config.DATA_DIR / "processed" / "extract" / "milvus" / "chunks"

ingestor = ChunkIngestor(collection_name="medical_knowledge_base", backend="local")
stats = ingestor.ingest_dir(JSON_DIR)
print(stats)
