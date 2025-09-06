from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector


from lancedb.embeddings import register, TextEmbeddingFunction
import sentence_transformers
from typeguard import typechecked


@register("sentence-transformers")
class SentenceTransformerEmbeddings(TextEmbeddingFunction):
    name: str = "all-MiniLM-L6-v2"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ndims = None
        self._model = None

    @typechecked
    def generate_embeddings(self, texts: list[str]):
        if self._model is None:
            self._model = sentence_transformers.SentenceTransformer(self.name)
        return self._embedding_model().encode(texts).tolist()

    def ndims(self):
        if self._ndims is None:
            self._ndims = len(self.generate_embeddings(["foo"])[0])
        return self._ndims

    def _embedding_model(self):
        return self._model


def get_embedding_func():
    return get_registry().get("sentence-transformers").create(name="all-MiniLM-L6-v2")


def get_embedding(text: str):
    func = get_embedding_func()
    return func.embed_query(text)


model = get_embedding_func()


class Chat(LanceModel):
    user: str
    agent: str
    text: str = model.SourceField()
    embedding: Vector(model.ndims()) = model.VectorField()
