from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector


def get_embedding_func():
    return (
        get_registry()
        .get("sentence-transformers")
        .create(name="google/embeddinggemma-300M")
    )


def get_embedding(text: str):
    func = get_embedding_func()
    return func.embed_query(text)


model = get_embedding_func()


class Chat(LanceModel):
    user: str
    agent: str
    text: str = model.SourceField()
    embedding: Vector(model.ndims()) = model.VectorField()
