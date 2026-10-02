from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from openai import OpenAI

from app.config import get_settings
from app.services.processing.models import ContractRepresentation
from app.services.retrieval.models import RetrievalComparison, RetrievedChunk
from app.services.relationships.models import ContractGraph
from app.services.structure.models import DocumentStructure, StructuralChunk


class ContractRetriever:
    """Return a vector-only baseline and a one-hop graph-expanded context."""

    EMBEDDING_CACHE_VERSION = "v1"

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.embedding_model
        self.client = OpenAI(
            base_url=settings.ollama_base_url,
            api_key="ollama",
            timeout=120.0,
            max_retries=1,
        )
        self.cache_dir = Path(".cache") / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def compare(
        self,
        *,
        query: str,
        document_key: str,
        representation: ContractRepresentation,
        top_k: int = 5,
    ) -> RetrievalComparison:
        if not query.strip():
            raise ValueError("query must not be empty.")
        if top_k < 1:
            raise ValueError("top_k must be greater than 0.")

        chunks = representation.structure.chunks
        if not chunks:
            raise ValueError("Document structure contains no chunks.")

        ranked_chunks, scores = self._rank_vector_chunks(
            document_key=document_key,
            chunks=chunks,
            query=query,
        )
        chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        baseline_ids = [chunk.chunk_id for chunk in ranked_chunks[:top_k]]
        baseline_id_set = set(baseline_ids)

        expansion_reasons = self._expand_from_graph(
            initial_chunk_ids=baseline_ids,
            graph=representation.graph,
        )
        graph_ids = list(baseline_ids)
        graph_ids.extend(
            chunk_id
            for chunk_id in sorted(
                expansion_reasons,
                key=lambda item: scores.get(item, float("-inf")),
                reverse=True,
            )
            if chunk_id in chunks_by_id and chunk_id not in graph_ids
        )
        added_chunk_ids = [
            chunk_id for chunk_id in graph_ids if chunk_id not in baseline_id_set
        ]

        return RetrievalComparison(
            query=query,
            embedding_model=self.model,
            baseline=[
                self._to_result(chunks_by_id[chunk_id], scores[chunk_id])
                for chunk_id in baseline_ids
            ],
            graph_augmented=[
                self._to_result(
                    chunks_by_id[chunk_id],
                    scores[chunk_id],
                    (
                        expansion_reasons.get(chunk_id, {})
                        if chunk_id in added_chunk_ids
                        else {}
                    ),
                )
                for chunk_id in graph_ids
            ],
            graph_added_chunk_ids=added_chunk_ids,
        )

    def retrieve_vector(
        self,
        *,
        query: str,
        document_key: str,
        structure: DocumentStructure,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Retrieve chunks by vector similarity without loading semantics or graph."""
        if not query.strip():
            raise ValueError("query must not be empty.")
        if top_k < 1:
            raise ValueError("top_k must be greater than 0.")
        if not structure.chunks:
            raise ValueError("Document structure contains no chunks.")

        ranked_chunks, _ = self._rank_vector_chunks(
            document_key=document_key,
            chunks=structure.chunks,
            query=query,
        )
        return ranked_chunks[:top_k]

    def _rank_vector_chunks(
        self,
        *,
        document_key: str,
        chunks: list[StructuralChunk],
        query: str,
    ) -> tuple[list[RetrievedChunk], dict[int, float]]:
        vectors = self._get_chunk_embeddings(document_key, chunks)
        query_vector = self._embed([query])[0]
        scores = {
            chunk.chunk_id: self._cosine(query_vector, vectors[chunk.chunk_id])
            for chunk in chunks
        }
        chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        ranked_ids = sorted(scores, key=scores.get, reverse=True)
        return (
            [
                self._to_result(chunks_by_id[chunk_id], scores[chunk_id])
                for chunk_id in ranked_ids
            ],
            scores,
        )

    def _get_chunk_embeddings(
        self,
        document_key: str,
        chunks: list[StructuralChunk],
    ) -> dict[int, list[float]]:
        result = {}
        missing = []
        for chunk in chunks:
            cache_path = self._embedding_cache_path(
                document_key,
                chunk.chunk_id,
                chunk.text,
            )
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                vector = cached.get("vector") if isinstance(cached, dict) else None
                if (
                    isinstance(cached, dict)
                    and cached.get("model") == self.model
                    and cached.get("version") == self.EMBEDDING_CACHE_VERSION
                    and isinstance(vector, list)
                    and bool(vector)
                    and all(isinstance(value, (int, float)) for value in vector)
                ):
                    result[chunk.chunk_id] = vector
                    continue
            except (OSError, json.JSONDecodeError, TypeError):
                pass
            missing.append((chunk, cache_path))

        if missing:
            vectors = self._embed([chunk.text for chunk, _ in missing])
            if len(vectors) != len(missing):
                raise ValueError(
                    "Embedding service returned an unexpected vector count."
                )
            for (chunk, cache_path), vector in zip(missing, vectors):
                result[chunk.chunk_id] = vector
                cache_path.write_text(
                    json.dumps(
                        {
                            "model": self.model,
                            "version": self.EMBEDDING_CACHE_VERSION,
                            "vector": vector,
                        }
                    ),
                    encoding="utf-8",
                )
        return result

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [
            item.embedding
            for item in sorted(response.data, key=lambda item: item.index)
        ]

    def _embedding_cache_path(
        self,
        document_key: str,
        chunk_id: int,
        text: str,
    ) -> Path:
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = hashlib.sha256(
            (
                f"{self.EMBEDDING_CACHE_VERSION}:{document_key}:"
                f"{self.model}:{chunk_id}:{text_hash}"
            ).encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{cache_key}.json"

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            raise ValueError("Embedding dimensions do not match.")
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)

    @staticmethod
    def _expand_from_graph(
        *,
        initial_chunk_ids: list[int],
        graph: ContractGraph,
    ) -> dict[int, dict[str, list[str]]]:
        entities = {entity.entity_id: entity for entity in graph.entities}
        chunk_to_entities = {}
        for entity in graph.entities:
            for chunk_id in entity.chunk_ids:
                chunk_to_entities.setdefault(chunk_id, set()).add(entity.entity_id)

        expanded = {}
        for chunk_id in initial_chunk_ids:
            connected_ids = set(chunk_to_entities.get(chunk_id, set()))
            for relationship in graph.relationships:
                if relationship.relationship_type not in {"references", "defines"}:
                    continue

                if relationship.source_entity_id in connected_ids:
                    neighbor_id = relationship.target_entity_id
                    reason = relationship.relationship_type
                elif relationship.target_entity_id in connected_ids:
                    neighbor_id = relationship.source_entity_id
                    reason = f"incoming_{relationship.relationship_type}"
                else:
                    continue

                neighbor = entities.get(neighbor_id)
                if neighbor is None:
                    continue
                evidence = relationship.source_text or ""
                for related_chunk_id in neighbor.chunk_ids:
                    if related_chunk_id != chunk_id:
                        item = expanded.setdefault(
                            related_chunk_id,
                            {"reasons": set(), "evidence": set()},
                        )
                        item["reasons"].add(reason)
                        if evidence:
                            item["evidence"].add(evidence)

        return {
            chunk_id: {
                "reasons": sorted(item["reasons"]),
                "evidence": sorted(item["evidence"]),
            }
            for chunk_id, item in expanded.items()
        }

    @staticmethod
    def _to_result(
        chunk: StructuralChunk,
        score: float,
        expansion: dict[str, list[str]] | None = None,
    ) -> RetrievedChunk:
        expansion = expansion or {}
        return RetrievedChunk(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            score=score,
            headings=chunk.headings,
            pages=chunk.pages,
            added_via=expansion.get("reasons", []),
            graph_evidence=expansion.get("evidence", []),
        )
