from __future__ import annotations

from openai import BadRequestError, OpenAI
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from src.config import Settings, _max_dimensions_for_model, get_settings
from src.models import Chunk


class Embedder:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = OpenAI(api_key=self._settings.openai_api_key)

    def embed_chunks(self, chunks: list[Chunk]) -> dict[str, list[float]]:
        vectors: dict[str, list[float]] = {}
        batch_size = self._settings.embedding_batch_size

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            inputs = [_embedding_input(chunk) for chunk in batch]
            response = self._create_embeddings(inputs)
            for chunk, item in zip(batch, response.data, strict=True):
                vectors[chunk.id] = list(item.embedding)

        return vectors

    def embed_query(self, query: str) -> list[float]:
        response = self._create_embeddings([query])
        return list(response.data[0].embedding)

    @retry(
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(5),
        retry=retry_if_not_exception_type(BadRequestError),
    )
    def _create_embeddings(self, inputs: list[str]):
        kwargs: dict = {
            "model": self._settings.openai_embedding_model,
            "input": inputs,
        }
        # Matryoshka shortening; omit when using the model's native width.
        max_dims = _max_dimensions_for_model(self._settings.openai_embedding_model)
        if self._settings.embedding_dimensions < max_dims:
            kwargs["dimensions"] = self._settings.embedding_dimensions
        return self._client.embeddings.create(**kwargs)


def _embedding_input(chunk: Chunk) -> str:
    if chunk.section_path:
        return f"{chunk.section_path}\n{chunk.raw_text}"
    return chunk.raw_text
