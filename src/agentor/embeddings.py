from typing import List, Union


class Embeddings:
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model

    def embed(self, input: Union[str, List[str]]):
        """Embed the input text using the model.
        Args:
            input: The input text to embed. Can be a single string or a list of strings.
        Returns:
            The embeddings of the input text.
        """
        from litellm import embedding

        if isinstance(input, str):
            input = [input]

        n = len(input)
        try:
            data = embedding(model=self.model, input=input).data
            if n == 1:
                return [data[0]["embedding"]]

            else:
                data = [data[i]["embedding"] for i in range(n)]
        except Exception as e:
            raise e
        return data
