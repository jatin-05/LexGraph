from fastapi import FastAPI, File, HTTPException, UploadFile

from app.config import get_settings
from app.db.supabase import supabase
from app.services.parsing.document_parser import parse_pdf
from app.services.structure.clause_segmenter import build_sections
from app.services.document.converter import DocumentConverterService
from app.services.processing.pipeline import process_contract
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

@app.post("/debug/contract-graph")
async def contract_graph_debug(
    file: UploadFile = File(...),
):
    file_bytes = await file.read()

    try:
        return process_contract(
            file_bytes=file_bytes,
            filename=file.filename or "contract.pdf",
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Contract processing failed: {exc}",
        ) from exc