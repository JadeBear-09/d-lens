import logging
import uuid

from app.core.config import Settings, get_settings
from app.schemas.report import FailureReport, SimilarReport
from app.services.embeddings import EmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)


class VectorStore:
    def upsert_report(self, report: FailureReport) -> None:
        raise NotImplementedError

    def search_similar(self, report: FailureReport, limit: int = 5) -> list[SimilarReport]:
        raise NotImplementedError


class QdrantVectorStore(VectorStore):
    def __init__(
        self,
        settings: Settings | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedding_provider = embedding_provider or get_embedding_provider(self.settings)
        self.client = None

        if self.settings.qdrant_url:
            try:
                from qdrant_client import QdrantClient

                self.client = QdrantClient(url=self.settings.qdrant_url, timeout=2)
            except Exception as exc:  # pragma: no cover - dependency/environment specific
                logger.warning("Qdrant client disabled: %s", exc)

    def upsert_report(self, report: FailureReport) -> None:
        if self.client is None:
            return

        text = report_to_text(report)
        vector = self.embedding_provider.embed_text(text)

        try:
            self._ensure_collection(len(vector))
            from qdrant_client.models import PointStruct

            self.client.upsert(
                collection_name=self.settings.qdrant_collection,
                points=[
                    PointStruct(
                        id=point_id(report.trace_id),
                        vector=vector,
                        payload=report.model_dump(mode="json"),
                    )
                ],
            )
        except Exception as exc:  # pragma: no cover - Qdrant availability varies
            logger.warning("Qdrant upsert skipped for trace %s: %s", report.trace_id, exc)

    def search_similar(self, report: FailureReport, limit: int = 5) -> list[SimilarReport]:
        if self.client is None:
            return []

        text = report_to_text(report)
        vector = self.embedding_provider.embed_text(text)

        try:
            self._ensure_collection(len(vector))
            hits = self.client.search(
                collection_name=self.settings.qdrant_collection,
                query_vector=vector,
                limit=limit + 1,
                with_payload=True,
            )
        except Exception as exc:  # pragma: no cover - Qdrant availability varies
            logger.warning("Qdrant search skipped for trace %s: %s", report.trace_id, exc)
            return []

        similar: list[SimilarReport] = []
        for hit in hits:
            payload = hit.payload or {}
            if payload.get("trace_id") == report.trace_id:
                continue
            similar.append(
                SimilarReport(
                    **payload,
                    similarity_score=max(0.0, min(float(hit.score), 1.0)),
                )
            )
            if len(similar) >= limit:
                break

        return similar

    def _ensure_collection(self, vector_size: int) -> None:
        assert self.client is not None
        from qdrant_client.models import Distance, VectorParams

        exists = self.client.collection_exists(self.settings.qdrant_collection)
        if exists:
            return

        self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def report_to_text(report: FailureReport) -> str:
    return " ".join(
        [
            report.failure_type,
            report.severity,
            report.root_cause,
            " ".join(report.evidence),
            " ".join(report.suggested_actions),
        ]
    )


def point_id(trace_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"dlens:{trace_id}"))
