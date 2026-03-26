from core.intelligence.embedding_engine import EmbeddingEngine

engine = EmbeddingEngine()

result = engine.embed_chunk(1)

print(result)
