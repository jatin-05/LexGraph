from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from app.services.extraction.models import ContractSemantics
from app.services.relationships.models import (
    ContractEntity,
    ContractGraph,
    ContractRelationship,
    ReferenceResolution,
)
from app.services.structure.models import DocumentStructure


_SECTION_LOCATOR = re.compile(r"(?<![\w.])(\d+(?:\.\d+)*)(?![\w.])")


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w.]+", " ", value).split())


def _stable_id(entity_type: str, document_key: str, identity: str) -> str:
    raw = f"{document_key}:{entity_type}:{_normalize(identity)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{entity_type}:{digest}"


def _relationship_id(
    relationship_type: str,
    source_entity_id: str,
    target_entity_id: str,
    source_chunk_id: int | None,
    source_text: str | None,
) -> str:
    raw = json.dumps(
        [
            relationship_type,
            source_entity_id,
            target_entity_id,
            source_chunk_id,
            source_text,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"relationship:{digest}"


class ContractGraphBuilder:
    """Build a small, evidence-linked graph without additional LLM calls."""

    def build(
        self,
        *,
        document_key: str,
        structure: DocumentStructure,
        semantics: ContractSemantics,
        reference_resolutions: list[ReferenceResolution],
    ) -> ContractGraph:
        entities: dict[str, ContractEntity] = {}
        relationships: dict[str, ContractRelationship] = {}
        section_id_by_locator: dict[str, list[str]] = {}
        section_ids_by_chunk: dict[int, list[str]] = {}
        term_id_by_name: dict[str, str] = {}

        document_id = _stable_id("document", document_key, "document")
        entities[document_id] = ContractEntity(
            entity_id=document_id,
            entity_type="document",
            value=structure.filename,
            filename=structure.filename,
        )

        for section in structure.sections:
            section_identity = section.locator or section.heading
            section_id = _stable_id("section", document_key, section_identity)
            existing = entities.get(section_id)
            if existing is None:
                entities[section_id] = ContractEntity(
                    entity_id=section_id,
                    entity_type="section",
                    value=section.heading,
                    locator=section.locator,
                    title=section.title,
                    chunk_ids=list(section.chunk_ids),
                )
            else:
                existing.chunk_ids = sorted(
                    set(existing.chunk_ids).union(section.chunk_ids)
                )

            if section.locator:
                section_id_by_locator.setdefault(
                    _normalize(section.locator), []
                ).append(section_id)

            for chunk_id in section.chunk_ids:
                section_ids_by_chunk.setdefault(chunk_id, []).append(section_id)

            self._add_relationship(
                relationships,
                relationship_type="contains_section",
                source_entity_id=document_id,
                source_entity_type="document",
                target_entity_id=section_id,
                target_entity_type="section",
            )

        for term in semantics.defined_terms:
            term_key = _normalize(term.term)
            term_id = term_id_by_name.get(term_key)
            if term_id is None:
                term_id = _stable_id("defined_term", document_key, term.term)
                term_id_by_name[term_key] = term_id
                entities[term_id] = ContractEntity(
                    entity_id=term_id,
                    entity_type="defined_term",
                    value=term.term,
                    definition=term.definition,
                    chunk_ids=(
                        [term.source_chunk_id]
                        if term.source_chunk_id is not None
                        else []
                    ),
                )
            else:
                entity = entities[term_id]
                if entity.definition is None and term.definition:
                    entity.definition = term.definition
                if term.source_chunk_id is not None:
                    entity.chunk_ids = sorted(
                        set(entity.chunk_ids).union([term.source_chunk_id])
                    )

            if (
                not term.definition
                or not term.source_text.strip()
                or term.source_chunk_id is None
            ):
                continue

            source_entity_id, source_entity_type = self._source_section(
                chunk_id=term.source_chunk_id,
                section_ids_by_chunk=section_ids_by_chunk,
                entities=entities,
                document_id=document_id,
            )
            self._add_relationship(
                relationships,
                relationship_type="defines",
                source_entity_id=source_entity_id,
                source_entity_type=source_entity_type,
                target_entity_id=term_id,
                target_entity_type="defined_term",
                source_chunk_id=term.source_chunk_id,
                source_text=term.source_text,
            )

        reference_by_index = {
            index: reference
            for index, reference in enumerate(semantics.references)
        }
        for resolution in reference_resolutions:
            if resolution.status != "resolved":
                continue

            reference = reference_by_index.get(resolution.reference_index)
            if (
                reference is None
                or reference.source_chunk_id is None
                or not reference.source_text.strip()
            ):
                continue

            source_entity_id, source_entity_type = self._source_section(
                chunk_id=reference.source_chunk_id,
                section_ids_by_chunk=section_ids_by_chunk,
                entities=entities,
                document_id=document_id,
            )

            if resolution.target_kind == "section":
                target_entity_id = self._section_target_id(
                    resolution=resolution,
                    document_key=document_key,
                    section_id_by_locator=section_id_by_locator,
                    entities=entities,
                    relationships=relationships,
                    document_id=document_id,
                )
                target_entity_type = "section"
            elif resolution.target_kind == "defined_term":
                target_name = resolution.resolved_target or resolution.target
                target_key = _normalize(target_name)
                target_entity_id = term_id_by_name.get(target_key)
                if target_entity_id is None:
                    matching_term = next(
                        (
                            term
                            for term in semantics.defined_terms
                            if _normalize(term.term) == target_key
                        ),
                        None,
                    )
                    if matching_term is None:
                        continue
                    target_entity_id = _stable_id(
                        "defined_term",
                        document_key,
                        matching_term.term,
                    )
                target_entity_type = "defined_term"
            else:
                continue

            self._add_relationship(
                relationships,
                relationship_type="references",
                source_entity_id=source_entity_id,
                source_entity_type=source_entity_type,
                target_entity_id=target_entity_id,
                target_entity_type=target_entity_type,
                source_chunk_id=reference.source_chunk_id,
                source_text=reference.source_text,
            )

        return ContractGraph(
            entities=sorted(entities.values(), key=lambda entity: entity.entity_id),
            relationships=sorted(
                relationships.values(),
                key=lambda relationship: relationship.relationship_id,
            ),
        )

    @staticmethod
    def _source_section(
        *,
        chunk_id: int,
        section_ids_by_chunk: dict[int, list[str]],
        entities: dict[str, ContractEntity],
        document_id: str,
    ) -> tuple[str, str]:
        candidates = [
            entities[entity_id]
            for entity_id in section_ids_by_chunk.get(chunk_id, [])
            if entity_id in entities
        ]
        if not candidates:
            return document_id, "document"

        # Prefer the most specific section when structure metadata contains
        # both a parent heading and a subsection for the same chunk.
        section = max(
            candidates,
            key=lambda item: item.locator.count(".") if item.locator else 0,
        )
        return section.entity_id, "section"

    @staticmethod
    def _section_target_id(
        *,
        resolution: ReferenceResolution,
        document_key: str,
        section_id_by_locator: dict[str, list[str]],
        entities: dict[str, ContractEntity],
        relationships: dict[str, ContractRelationship],
        document_id: str,
    ) -> str:
        locator_matches = list(
            dict.fromkeys(
                match.group(1)
                for match in _SECTION_LOCATOR.finditer(resolution.target)
            )
        )
        if len(locator_matches) == 1:
            matches = list(dict.fromkeys(section_id_by_locator.get(
                _normalize(locator_matches[0]),
                [],
            )))
            if len(matches) == 1:
                entities[matches[0]].chunk_ids = sorted(
                    set(entities[matches[0]].chunk_ids).union(
                        resolution.target_chunk_ids
                    )
                )
                return matches[0]

        identity = resolution.resolved_target or resolution.target
        section_id = _stable_id("section", document_key, identity)
        if section_id not in entities:
            locator = locator_matches[0] if len(locator_matches) == 1 else None
            title = identity
            if locator and title.casefold().startswith(locator.casefold()):
                title = title[len(locator):].strip(" .") or None
            entities[section_id] = ContractEntity(
                entity_id=section_id,
                entity_type="section",
                value=identity,
                locator=locator,
                title=title,
                chunk_ids=list(resolution.target_chunk_ids),
            )
        else:
            entities[section_id].chunk_ids = sorted(
                set(entities[section_id].chunk_ids).union(
                    resolution.target_chunk_ids
                )
            )

        ContractGraphBuilder._add_relationship(
            relationships,
            relationship_type="contains_section",
            source_entity_id=document_id,
            source_entity_type="document",
            target_entity_id=section_id,
            target_entity_type="section",
        )
        return section_id

    @staticmethod
    def _add_relationship(
        relationships: dict[str, ContractRelationship],
        *,
        relationship_type: str,
        source_entity_id: str,
        source_entity_type: str,
        target_entity_id: str,
        target_entity_type: str,
        source_chunk_id: int | None = None,
        source_text: str | None = None,
    ) -> None:
        relationship_id = _relationship_id(
            relationship_type,
            source_entity_id,
            target_entity_id,
            source_chunk_id,
            source_text,
        )
        relationships[relationship_id] = ContractRelationship(
            relationship_id=relationship_id,
            relationship_type=relationship_type,
            source_entity_id=source_entity_id,
            source_entity_type=source_entity_type,
            target_entity_id=target_entity_id,
            target_entity_type=target_entity_type,
            source_chunk_id=source_chunk_id,
            source_text=source_text,
        )
