# Contract Intelligence System

A research-oriented legal contract intelligence system focused on **structure-aware and relationship-aware contract understanding**.

The goal is to go beyond "chat with a PDF" or simple vector RAG. The system first converts a contract into a structured, evidence-linked representation containing document structure, semantic facts, provenance, and eventually relationships between contractual provisions.

---

## 1. Project Goal

Legal contracts often contain information that is distributed across multiple sections.

For example, a termination provision may depend on:

- a definition introduced earlier in the agreement
- a cure period in another clause
- a referenced payment or breach provision
- exceptions or conditions defined elsewhere

The project is therefore being built around this idea:

> **Understand the structure and relationships inside a contract before using retrieval and question answering.**

The longer-term research goal is to compare conventional vector-based RAG with structure-aware / relationship-aware retrieval for contract question answering.

---

## 2. Current Architecture

```text
PDF / DOCX
     |
     v
  Docling
     |
     +---- document structure
     |      - headings
     |      - sections
     |      - chunks
     |      - pages
     |      - bounding boxes
     |      - provenance
     |
     v
 Cached Docling chunks
     |
     v
 Qwen2.5:3B-Instruct (local Ollama)
     |
     v
 Semantic extraction
     - parties
     - defined terms
     - obligations
     - rights
     - references
     |
     v
 Deterministic Validator V1
     |
     v
 Contract Representation
     |
     v
 [Next]
 Reference resolution
     |
     v
 Relationships
     |
     v
 [Future]
 Structure-aware / relationship-aware retrieval
     |
     v
 [Future]
 Contract question answering + evidence
```

### Separation of responsibilities

**Docling** is responsible for document understanding and structure.

**Qwen2.5:3B-Instruct** is responsible for semantic extraction from individual chunks.

**The validator** performs deterministic checks on the LLM output. It does not use another LLM.

**The processing pipeline** combines the layers into the current contract representation.

---

## 3. Repository Structure

```text
contract-intelligence/
|
├── apps/
│   └── api/
│       |
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── config.py
│       │   |
│       │   ├── db/
│       │   │   ├── __init__.py
│       │   │   └── supabase.py
│       │   |
│       │   └── services/
│       │       |
│       │       ├── document/
│       │       │   ├── __init__.py
│       │       │   └── converter.py
│       │       |
│       │       ├── extraction/
│       │       │   ├── __init__.py
│       │       │   ├── models.py
│       │       │   └── extractor.py
│       │       |
│       │       ├── processing/
│       │       │   ├── __init__.py
│       │       │   ├── models.py
│       │       │   └── pipeline.py
│       │       |
│       │       ├── structure/
│       │       │   ├── __init__.py
│       │       │   ├── models.py
│       │       │   └── builder.py
│       │       |
│       │       └── validation/
│       │           ├── __init__.py
│       │           ├── models.py
│       │           └── semantic_validator.py
│       |
│       ├── .cache/
│       │   └── docling/
│       |
│       ├── .env
│       └── requirements.txt
|
└── README.md
```

### Old code that should not be required by the current architecture

The current implementation does not use the old graph-based pipeline.

Do not reintroduce old modules such as:

- `process_contract`
- `/debug/contract-graph`
- Docling Graph integration
- Neo4j
- the old custom PDF parsing / clause segmentation path

The current architecture deliberately keeps the implementation simpler until relationships demonstrate a need for a dedicated graph database.

---

## 4. Prerequisites

A new developer needs:

- Python 3.11+ recommended
- Git
- Ollama
- the Qwen model used by the project
- a Supabase project/environment if database functionality is needed

The current model is:

```text
qwen2.5:3b-instruct
```

The model runs locally through Ollama. No paid OpenAI, Gemini, or Mistral API key is required for the current extraction pipeline.

---

# 5. Windows Setup

These commands assume Windows PowerShell.

## 5.1 Clone the repository

```powershell
git clone <REPOSITORY_URL>
cd contract-intelligence
```

Replace `<REPOSITORY_URL>` with the repository URL.

---

## 5.2 Create and activate a virtual environment

From the repository root:

```powershell
cd apps\api
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, use the normal Windows Python launcher / terminal setup appropriate for your environment, or run the equivalent activation command from Command Prompt.

---

## 5.3 Install Python dependencies

```powershell
pip install -r requirements.txt
```

Current requirements are expected to include:

```text
fastapi[standard]
supabase
pydantic-settings
pymupdf
python-multipart
docling
instructor
```

If requirements change, always use the repository's current `requirements.txt` as the source of truth.

---

# 6. Install and prepare Ollama

Install Ollama on the development machine and make sure the Ollama service is running.

Pull the current project model:

```powershell
ollama pull qwen2.5:3b-instruct
```

Verify that the model is available:

```powershell
ollama list
```

You should see:

```text
qwen2.5:3b-instruct
```

The API expects Ollama to be available at:

```text
http://localhost:11434
```

The OpenAI-compatible base URL used by the project is:

```text
http://localhost:11434/v1
```

---

# 7. Environment Configuration

Create:

```text
apps/api/.env
```

Example:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_SECRET_KEY=your_supabase_secret_key

ENVIRONMENT=development

EXTRACTION_MODEL=qwen2.5:3b-instruct

OLLAMA_BASE_URL=http://localhost:11434/v1
```

## Important

Do **not** commit `.env` to Git.

The model name is configured through the environment:

```env
EXTRACTION_MODEL=qwen2.5:3b-instruct
```

`config.py` defines the application setting, while `.env` allows a developer to change the model without changing Python code.

The flow is:

```text
.env
  |
  v
config.py
  |
  v
extractor.py
  |
  v
Ollama
```

---

# 8. Start the API

From:

```text
apps/api
```

with the virtual environment activated:

```powershell
uvicorn app.main:app --reload
```

The API should be available at:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

OpenAPI JSON:

```text
http://127.0.0.1:8000/openapi.json
```

---

# 9. Health Checks

### API health

Open:

```text
GET /health
```

Expected response:

```json
{
  "status": "ok",
  "service": "Contract Intelligence API",
  "environment": "development"
}
```

### Supabase configuration

Open:

```text
GET /health/supabase
```

This checks that the Supabase client is configured.

---

# 10. Current Debug Endpoints

## `/debug/docling`

Purpose:

Inspect the raw Docling conversion.

This is useful for checking:

- extracted Markdown
- document structure
- raw document elements
- provenance information

---

## `/debug/extract-chunk`

Purpose:

Run semantic extraction on a single chunk.

Typical development test:

```text
chunk_index = 0
validate = true
force_refresh = false
```

This is useful for testing the Qwen prompt and schema without processing the entire contract.

### Parameters

`chunk_index`

```text
0, 1, 2, ...
```

Selects which chunk is sent to Qwen.

`validate`

```text
true / false
```

When `true`:

```text
Qwen
  |
  v
Validator V1
  |
  v
validated extraction
```

When `false`:

```text
Qwen
  |
  v
raw extraction
```

This toggle exists so model behavior and validator behavior can be inspected separately.

`force_refresh`

```text
true / false
```

When `true`, the cached Docling result is ignored and the document is parsed again.

---

## `/debug/extract-contract`

Purpose:

Process multiple or all semantic chunks.

Example:

```text
max_chunks = 3
validate = true
force_refresh = false
```

### Important behavior of `max_chunks`

`max_chunks` currently limits **semantic extraction**, not Docling parsing.

For example:

```text
max_chunks = 1
```

means:

```text
Docling:
    parse the entire document
    build the full structural representation

Qwen:
    process chunk 0 only
```

Leaving `max_chunks` empty means all chunks are sent through semantic extraction.

This is intentional during development because we want the complete document structure even when only a subset of chunks is being tested with the LLM.

---

# 11. Docling Cache

Docling output is cached locally under:

```text
apps/api/.cache/docling/
```

A document-specific hash is used as the cache key.

Conceptually:

```text
Contract A
   |
   v
hash A
   |
   v
.cache/docling/hashA.json
```

and:

```text
Contract B
   |
   v
hash B
   |
   v
.cache/docling/hashB.json
```

The same document can therefore be uploaded repeatedly without reparsing it with Docling.

### Cache behavior

First run:

```text
cache miss
    |
    v
Docling conversion
    |
    v
chunking
    |
    v
cache saved
```

Later run:

```text
cache hit
    |
    v
cached chunks loaded
    |
    v
Docling conversion skipped
```

`force_refresh=true` bypasses the cache.

### Cache version

The pipeline contains a cache version such as:

```python
CACHE_VERSION = "v1"
```

If the Docling/chunking representation changes in a way that makes old cache files incompatible, increment the version.

---

# 12. Current Contract Representation

The current result separates structure and semantics.

```text
ContractRepresentation
|
├── structure
|   ├── sections
|   └── chunks
|       └── provenance
|
├── semantics
|   ├── parties
|   ├── defined_terms
|   ├── obligations
|   ├── rights
|   └── references
|
└── validation
    └── issues
```

## Structure

The structure layer is derived from Docling output.

It contains information such as:

- headings
- section relationships to chunks
- page numbers
- bounding boxes
- provenance

## Semantics

The semantic layer is generated by Qwen.

It contains:

- parties
- defined terms
- obligations
- rights
- references

## Validation

Validation V1 is deterministic Python logic.

It does not use an LLM.

---

# 13. Provenance

Provenance answers:

> Where did this information come from in the original document?

A semantic fact can retain a `source_chunk_id`.

The structural chunk retains information such as:

```text
page number
bounding box
document element reference
```

Conceptually:

```text
Fact
 |
 v
source_chunk_id
 |
 v
Chunk
 |
 v
Provenance
 |
 +--> page
 |
 +--> bounding box
 |
 v
Original PDF location
```

This is important for future evidence-grounded answers and PDF highlighting.

---

# 14. Development Workflow

Recommended development loop:

```text
1. Start Ollama
2. Start FastAPI
3. Open /docs
4. Upload a test contract
5. Inspect /debug/docling
6. Test /debug/extract-chunk
7. Compare validate=true vs validate=false
8. Test /debug/extract-contract with a small max_chunks value
9. Inspect structure + semantics + validation
10. Run the full contract once the small tests are stable
```

A good first document for development is:

```text
master-saas-agreement.pdf
```

or another representative legal contract.

---

# 15. Current Research Direction

The current system is the foundation for a larger research question:

> Can contract-aware retrieval outperform conventional vector-based RAG on questions that require evidence from multiple related clauses?

The planned progression is:

```text
Document parsing
      |
      v
Semantic extraction
      |
      v
Validation
      |
      v
Normalization
      |
      v
Reference resolution
      |
      v
Relationships
      |
      v
Structure-aware retrieval
      |
      v
Contract question answering
      |
      v
Evaluation
```

---

# 16. Next Development Phase

The next planned component is **reference resolution and relationships**.

For example:

```text
Termination
    |
    +---- references ----> Material Breach
                              |
                              +---- defined_in ----> Section 1.x
```

Initial relationship types may include:

```text
defines
references
applies_to
```

Later candidates include:

```text
depends_on
modifies
exception_to
grants
imposes
```

The first implementation is expected to use structured relational data rather than immediately requiring Neo4j.

---

# 17. Future Retrieval Layer

The planned retrieval system will combine multiple signals:

```text
semantic similarity
+
keyword / lexical retrieval
+
document structure
+
contract relationships
```

Instead of only:

```text
question
  |
  v
vector search
  |
  v
answer
```

the goal is:

```text
question
  |
  v
relevant clause
  |
  +--> related definition
  |
  +--> referenced section
  |
  +--> related obligation
  |
  v
supporting evidence
  |
  v
answer
```

The final system should be able to present both an answer and the evidence path supporting it.

---

# 18. Testing Philosophy

The project is intentionally being built in small layers.

Do not assume that a correct final answer means the whole pipeline is correct.

The following stages should be independently inspectable:

```text
PDF parsing quality
        |
        v
chunking quality
        |
        v
semantic extraction quality
        |
        v
validation quality
        |
        v
relationship quality
        |
        v
retrieval quality
        |
        v
answer quality
```

This separation is important for research and debugging.

---

# 19. Git / Repository Hygiene

Do not commit:

```text
.env
.cache/
__pycache__/
*.pyc
.venv/
```

A typical `.gitignore` should include:

```gitignore
.env
.cache/
.venv/
__pycache__/
*.pyc
```

Do not commit secrets, API credentials, or local model/cache artifacts.

---

# 20. Troubleshooting

## FastAPI starts but the endpoint is missing

Confirm the server was started from:

```text
apps/api
```

with:

```powershell
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

---

## `ContractProcessingPipeline` method errors

If you see an error such as:

```text
'ContractProcessingPipeline' object has no attribute 'extract_contract'
```

check that `pipeline.py` contains the current method and that `main.py` imports:

```python
from app.services.processing.pipeline import ContractProcessingPipeline
```

---

## Pydantic validation errors

These usually indicate that the Qwen output does not match the current extraction schema.

Check:

```text
apps/api/app/services/extraction/models.py
apps/api/app/services/extraction/extractor.py
```

The prompt and schema must agree on required fields.

---

## Qwen is unavailable

Check Ollama:

```powershell
ollama list
```

and make sure:

```text
qwen2.5:3b-instruct
```

is installed.

Also verify that Ollama is running.

---

## Extraction is slow

The major components are:

```text
Docling conversion
+
Qwen inference
```

Docling results are cached locally, so repeated processing of the same document should skip the expensive Docling conversion.

To intentionally re-run Docling:

```text
force_refresh = true
```

---

# 21. Current Status

The following components are currently implemented:

```text
[completed] FastAPI backend
[completed] Docling document conversion
[completed] Hybrid chunking
[completed] Docling caching
[completed] Document structure representation
[completed] Provenance tracking
[completed] Local Ollama integration
[completed] Qwen2.5:3B-Instruct extraction
[completed] Pydantic structured output
[completed] Structure / semantics separation
[completed] Semantic Validator V1
```

Current / upcoming:

```text
[in progress] Full-contract semantic processing
[next]        Normalization
[next]        Reference resolution
[next]        Relationship representation
[planned]     Structure-aware retrieval
[planned]     Contract question answering
[planned]     Evidence / PDF highlighting
[planned]     Evaluation against baseline vector RAG
```

---

# 22. For a New Contributor

If you are setting up the project for the first time, the minimum path is:

```text
1. Clone repository
2. Create Python virtual environment
3. Install requirements
4. Install/start Ollama
5. Pull qwen2.5:3b-instruct
6. Create apps/api/.env
7. Start FastAPI
8. Open /docs
9. Test /debug/docling
10. Test /debug/extract-chunk
11. Test /debug/extract-contract
```

Start with a small semantic test:

```text
max_chunks = 1
validate = true
force_refresh = false
```

Then increase:

```text
max_chunks = 3
```

and eventually leave `max_chunks` empty to process all chunks.

---

## 23. Important Design Principle

The project is intentionally **not** built as:

```text
PDF
  |
  v
embeddings
  |
  v
vector database
  |
  v
chatbot
```

Instead:

```text
PDF
  |
  v
document understanding
  |
  v
structure + semantics + provenance
  |
  v
relationships
  |
  v
retrieval
  |
  v
evidence-grounded reasoning
```

This representation-first approach is the core technical direction of the project.
