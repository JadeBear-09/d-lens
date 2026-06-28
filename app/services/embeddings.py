import hashlib
import math
import re
from typing import Protocol

from app.core.config import Settings, get_settings


class EmbeddingProvider(Protocol):
    def embed_text(self, text: str) -> list[float]:
        """Return vector representation for text."""


class HashEmbeddingProvider:
    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class OpenAIEmbeddingProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        from openai import OpenAI

        self.client = OpenAI(api_key=self.settings.openai_api_key)

    def embed_text(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=text,
        )
        return response.data[0].embedding


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    active_settings = settings or get_settings()
    if active_settings.llm_online:
        return OpenAIEmbeddingProvider(active_settings)
    return HashEmbeddingProvider()
