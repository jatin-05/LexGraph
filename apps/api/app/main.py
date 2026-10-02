from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.db.supabase import supabase
from app.services.parsing.document_parser import parse_pdf
from app.services.structure.clause_segmenter import build_sections
from app.services.document.converter import DocumentConverterService
from app.services.processing.pipeline import ContractProcessingPipeline
from app.services.retrieval.answerer import ContractAnswerer
from app.services.retrieval.models import ContractQuestionResponse
from app.services.retrieval.retriever import ContractRetriever

import logging
from colorlog import ColoredFormatter

formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)

handler = logging.StreamHandler()
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)


processing_pipeline = ContractProcessingPipeline()
contract_retriever = ContractRetriever()
contract_answerer = ContractAnswerer()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/health/supabase")
def supabase_health_check():
    return {
        "status": "configured",
        "supabase_url": settings.supabase_url,
        "client_initialized": supabase is not None,
    }


@app.post("/debug/parse-pdf")
async def parse_pdf_endpoint(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    file_bytes = await file.read()

    try:
        document = parse_pdf(
            file_bytes=file_bytes,
            filename=file.filename or "unknown.pdf",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return document

@app.post("/debug/build-structure")
async def build_structure_endpoint(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    file_bytes = await file.read()

    try:
        document = parse_pdf(
            file_bytes=file_bytes,
            filename=file.filename or "unknown.pdf",
        )

        sections = build_sections(
            document_id=document.document_id,
            pages=document.pages,
        )

        return {
            "document_id": document.document_id,
            "sections": sections,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


document_converter = DocumentConverterService()


@app.post("/debug/docling")
async def docling_debug(file: UploadFile = File(...)):
    file_bytes = await file.read()

    try:
        document = document_converter.convert(
            file_bytes=file_bytes,
            filename=file.filename or "document.pdf",
        )

        return {
            "document_type": type(document).__name__,
            "markdown": document.export_to_markdown(),
            "document_json": document.export_to_dict(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post("/debug/extract-chunk")
async def extract_chunk_debug(
    file: UploadFile = File(...),
    chunk_index: int = 0,
    force_refresh: bool = False,
):
    file_bytes = await file.read()

    try:
        return processing_pipeline.extract_chunk(
            file_bytes=file_bytes,
            filename=file.filename or "contract.pdf",
            chunk_index=chunk_index,
            force_refresh=force_refresh,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {exc}",
        ) from exc

@app.post("/debug/extract-contract")
async def extract_contract_debug(
    file: UploadFile = File(...),
    max_chunks: int | None = None,
    force_refresh: bool = False,
    validate: bool = True,
):
    file_bytes = await file.read()

    try:
        return processing_pipeline.extract_contract(
            file_bytes=file_bytes,
            filename=file.filename or "contract.pdf",
            max_chunks=max_chunks,
            force_refresh=force_refresh,
            validate=validate,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Contract extraction failed: {exc}",
        ) from exc


@app.post("/ask-contract", response_model=ContractQuestionResponse)
async def ask_contract(
    file: UploadFile = File(...),
    query: str = Form(...),
    top_k: int = Form(5),
    use_relationship_graph: bool = Form(False),
    semantic_model: str = Form("local_qwen"),
    answer_model: str = Form("local_qwen"),
):
    file_bytes = await file.read()
    filename = file.filename or "contract.pdf"

    try:
        document_key = processing_pipeline._cache_key(file_bytes, filename)
        if use_relationship_graph:
            representation = processing_pipeline.extract_contract(
                file_bytes=file_bytes,
                filename=filename,
                semantic_model=semantic_model,
            )
            comparison = contract_retriever.compare(
                query=query,
                document_key=document_key,
                representation=representation,
                top_k=top_k,
            )
            retrieved_chunks = comparison.graph_augmented
            retrieval_mode = "graph"
            graph_added_chunk_ids = comparison.graph_added_chunk_ids
            embedding_model = comparison.embedding_model
        else:
            structure = processing_pipeline.extract_structure(
                file_bytes=file_bytes,
                filename=filename,
            )
            retrieved_chunks = contract_retriever.retrieve_vector(
                query=query,
                document_key=document_key,
                structure=structure,
                top_k=top_k,
            )
            retrieval_mode = "chunks"
            graph_added_chunk_ids = []
            embedding_model = contract_retriever.model

        answerer = ContractAnswerer(answer_model)
        answer = answerer.answer(
            query=query,
            chunks=retrieved_chunks,
        )
        return ContractQuestionResponse(
            query=query,
            embedding_model=embedding_model,
            answer_model=answerer.model,
            retrieval_mode=retrieval_mode,
            answer=answer,
            retrieved_chunks=retrieved_chunks,
            graph_added_chunk_ids=graph_added_chunk_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Contract question answering failed")
        raise HTTPException(
            status_code=500,
            detail=(
                "Contract question failed. Confirm the selected model service "
                "and embedding service are configured and available."
            ),
        ) from exc


@app.post("/debug/retrieve-contract")
async def compare_contract_retrieval(
    file: UploadFile = File(...),
    query: str = Form(...),
    top_k: int = Form(5),
    include_answers: bool = Form(True),
):
    file_bytes = await file.read()
    filename = file.filename or "contract.pdf"

    try:
        representation = processing_pipeline.extract_contract(
            file_bytes=file_bytes,
            filename=filename,
        )
        document_key = processing_pipeline._cache_key(file_bytes, filename)
        comparison = contract_retriever.compare(
            query=query,
            document_key=document_key,
            representation=representation,
            top_k=top_k,
        )
        if include_answers:
            comparison.answer_model = contract_answerer.model
            comparison.baseline_answer = contract_answerer.answer(
                query=query,
                chunks=comparison.baseline,
            )
            comparison.graph_answer = contract_answerer.answer(
                query=query,
                chunks=comparison.graph_augmented,
            )
        return comparison
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Contract retrieval comparison failed")
        raise HTTPException(
            status_code=500,
            detail=(
                "Retrieval comparison failed. Confirm Ollama is running and "
                "the configured embedding and extraction models are installed."
            ),
        ) from exc
