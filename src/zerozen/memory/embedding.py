from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector


def get_embedding_func():
    return (
        get_registry()
        .get("sentence-transformers")
        .create(name="google/embeddinggemma-300M", device="cpu")
    )


def get_embedding(text: str):
    func = get_embedding_func()
    return func.embed_query(text)


class EmbeddingSchema(LanceModel):
    role: str
    content: str
    embedding: Vector(
        dim=768,
    )
