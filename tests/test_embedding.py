from unittest.mock import MagicMock, patch

from agentor.embeddings import Embeddings


@patch(
    "agentor.embeddings.embedding",
    return_value=MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]}]),
)
def test_embeddings(mock_embedding):
    embeddings = Embeddings()
    resp = embeddings.embed(["Hello, world!"])
    assert len(resp) == 1
    assert len(resp[0]) == 3
    mock_embedding.assert_called_once_with(
        model="text-embedding-3-small", input=["Hello, world!"]
    )


@patch(
    "agentor.embeddings.embedding",
    return_value=MagicMock(
        data=[{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]
    ),
)
def test_embeddings_list(mock_embedding):
    embeddings = Embeddings()
    resp = embeddings.embed(["Hello, world!", "hi"])
    assert len(resp) == 2
    assert len(resp[0]) == 3
    assert len(resp[1]) == 3
    mock_embedding.assert_called_once_with(
        model="text-embedding-3-small", input=["Hello, world!", "hi"]
    )
