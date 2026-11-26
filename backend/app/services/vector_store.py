from uuid import UUID

from qdrant_client import QdrantClient, models

from app.core.config import settings


class VectorStore:
    def __init__(self) -> None:
        self.client = (
            QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
            if settings.qdrant_url
            else None
        )

    @property
    def ready(self) -> bool:
        return self.client is not None

    def upsert(self, items: list[tuple[str, list[float], dict]]) -> None:
        if not self.client or not items:
            return
        vector_size = len(items[0][1])
        if not self.client.collection_exists(settings.qdrant_collection):
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )
        self.client.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                models.PointStruct(id=str(UUID(chunk_id)), vector=vector, payload=payload)
                for chunk_id, vector, payload in items
            ],
        )

    def search(self, vector: list[float], limit: int = 10) -> list[tuple[str, float]]:
        if not self.client or not self.client.collection_exists(settings.qdrant_collection):
            return []
        hits = self.client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=limit,
            with_payload=False,
        ).points
        return [(str(hit.id), float(hit.score)) for hit in hits]


vector_store = VectorStore()
