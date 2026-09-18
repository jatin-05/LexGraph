from fastapi import FastAPI, File, HTTPException, UploadFile

from app.config import get_settings
from app.db.supabase import supabase
from app.services.parsing.document_parser import parse_pdf
from app.services.structure.clause_segmenter import build_sections
from app.services.document.converter import DocumentConverterService
from app.services.processing.pipeline import ContractProcessingPipeline

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