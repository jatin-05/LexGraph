from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from docling_graph import PipelineConfig, run_pipeline

from app.config import get_settings
from app.services.contract.schema import Contract


def _make_json_safe(value: Any) -> Any:
    """
    Convert values returned by NetworkX / Pydantic into JSON-safe data.
    """

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if isinstance(value, dict):
        return {
            str(key): _make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_make_json_safe(item) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def process_contract(
    file_bytes: bytes,
    filename: str,
) -> dict[str, Any]:
    """
    Run one document through:

        PDF/DOCX
            ↓
        Docling
            ↓
        Contract schema extraction
            ↓
        Knowledge graph
    """

    if not file_bytes:
        raise ValueError("Document is empty.")

    settings = get_settings()

    # Keep the uploaded filename, but remove any path components.
    safe_filename = Path(filename).name or "contract.pdf"

    temp_dir = Path(
        tempfile.mkdtemp(prefix="contract_graph_")
    )

    source_path = temp_dir / safe_filename

    source_path.write_bytes(file_bytes)

    try:
        config = PipelineConfig(
            source=str(source_path),

            # Our legal ontology.
            template=Contract,

            # Use an LLM for semantic extraction.
            backend="llm",

            # Local Ollama — no paid API.
            inference="local",
            provider_override="ollama",
            model_override=settings.graph_model,

            # A contract is a multi-page connected document.
            processing_mode="many-to-one",

            # Rich contracts benefit from chunked extraction.
            use_chunking=False,

            # Dense extraction:
            # discover entities first, then populate them.
            # extraction_contract="dense",
            extraction_contract="direct",

            # Preserve source grounding.
            provenance="standard",

            # Keep everything inspectable while developing.
            debug=True,
            dump_to_disk=True,

            # CSV is easy to inspect during development.
            export_format="csv",

            # We can later switch this to a permanent output location.
            output_dir="outputs/contracts",
        )

        context = run_pipeline(config)

        graph = context.knowledge_graph

        if graph is None:
            raise RuntimeError(
                "Docling Graph did not produce a knowledge graph."
            )

        models = context.extracted_models or []

        nodes = []

        for node_id, node_data in graph.nodes(data=True):
            nodes.append(
                {
                    "id": str(node_id),
                    "data": _make_json_safe(node_data),
                }
            )

        edges = []

        for source, target, edge_data in graph.edges(data=True):
            edges.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "data": _make_json_safe(edge_data),
                }
            )

        return {
            "status": "success",
            "filename": safe_filename,

            "graph": {
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "nodes": nodes,
                "edges": edges,
            },

            "extracted_models": [
                {
                    "type": type(model).__name__,
                    "data": _make_json_safe(model),
                }
                for model in models
            ],

            "output_dir": str(context.output_dir)
            if context.output_dir
            else None,
        }

    finally:
        # The source PDF itself is temporary. Docling Graph's debug/export
        # artifacts remain in the configured output directory.
        shutil.rmtree(temp_dir, ignore_errors=True)