from __future__ import annotations

import instructor
from openai import OpenAI

from app.config import get_settings


MODEL_CHOICES = {"local_qwen", "groq_qwen"}
GROQ_QWEN_MODEL = "qwen/qwen3.8-27b"


def create_instructor_client(choice: str, task: str):
    """Build a structured-output client for one of the UI's model choices."""
    if choice not in MODEL_CHOICES:
        raise ValueError("Choose either local_qwen or groq_qwen.")

    settings = get_settings()
    if choice == "local_qwen":
        model = settings.extraction_model
        if task == "answer":
            model = settings.answer_model or settings.extraction_model
        return (
            instructor.from_provider(
                "ollama/qwen2.5",
                base_url=settings.ollama_base_url,
                mode=instructor.Mode.JSON,
            ),
            model,
        )

    if not settings.groq_api_key:
        raise ValueError(
            "Groq is selected but GROQ_API_KEY is not configured in apps/api/.env."
        )

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        timeout=180.0,
        max_retries=1,
    )
    return (
        instructor.from_openai(client, mode=instructor.Mode.JSON_SCHEMA),
        GROQ_QWEN_MODEL,
    )
