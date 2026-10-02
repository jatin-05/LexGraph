# LexGraph

LexGraph is a contract question-answering project. It turns a PDF contract into readable document chunks, optionally extracts structured contract information and links internal references, then retrieves evidence to answer questions with citations.

## Set up on a new Windows machine

These steps start the API and web app locally. Supabase is used for sign-in; uploaded contracts and processing caches remain local to the API machine.

### 1. Install prerequisites

Install:

- [Git for Windows](https://git-scm.com/downloads/win)
- [Python 3.13](https://www.python.org/downloads/) (enable **Add Python to PATH** in the installer)
- [Node.js 20.9 or newer](https://nodejs.org/)
- [Ollama for Windows](https://ollama.com/download)

Docling, used to parse PDFs, supports Python 3.13 in current releases. Next.js 16 requires Node.js 20.9 or newer.

Open PowerShell and clone the project:

```powershell
git clone https://github.com/jatin-05/LexGraph.git
cd LexGraph
```

### 2. Create the Supabase project

Create a project at [Supabase](https://supabase.com/) or use an existing one. In its project settings, find the project URL and API keys.

- The **URL** and **publishable/anon key** go in the web app environment file.
- The backend needs `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. Use the project’s secret key (or legacy `service_role` key if that is what the dashboard provides) in the API environment file only.
- Do not put the secret/service-role key in a `NEXT_PUBLIC_...` variable or expose it to the browser.
- No custom database table or Supabase Storage bucket is needed for this MVP. Supabase Auth manages its own user records.

If you want sign-up to work without email verification, turn off email confirmation in the Supabase Auth email provider settings.

### 3. Install API dependencies

In PowerShell, from the project root:

```powershell
cd apps\api
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run this once in that PowerShell window, then activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. Download and start the local models

Ollama supplies semantic extraction, answer generation, and embeddings when the local model option is selected. The embedding model remains local even when Groq is selected for extraction or answers.

```powershell
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
ollama list
```

Keep Ollama running while using the app. The default extraction concurrency is two requests. If Ollama struggles with concurrent requests on your machine, set `EXTRACTION_MAX_CONCURRENCY=1` in the API `.env` file.

### 5. Configure and start the API

Create `apps/api/.env` with your values:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SECRET_KEY=YOUR_SUPABASE_SECRET_OR_SERVICE_ROLE_KEY

OLLAMA_BASE_URL=http://localhost:11434/v1
EXTRACTION_MODEL=qwen2.5:3b
ANSWER_MODEL=qwen2.5:3b
EMBEDDING_MODEL=nomic-embed-text
EXTRACTION_MAX_CONCURRENCY=2

# Optional: needed only when selecting Groq models in the app
# GROQ_API_KEY=your_groq_api_key
```

Keep the virtual environment activated, and start the API from `apps/api`:

```powershell
uvicorn app.main:app --reload --port 8000
```

Check that `http://localhost:8000/health` responds. Interactive API documentation is at `http://localhost:8000/docs`.

### 6. Configure and start the web app

Open a **second** PowerShell window at the project root:

```powershell
cd web
Copy-Item .env.example .env.local
```

Edit `web/.env.local` and set:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_SUPABASE_PUBLISHABLE_OR_ANON_KEY
CONTRACT_API_URL=http://localhost:8000
```

Install the locked web dependencies and start Next.js:

```powershell
npm ci
npm run dev
```

Open `http://localhost:3000`, create an account, and sign in. Keep both the API and web terminal windows running.

### 7. Optional Groq models

The chat has **separate model selectors** for semantic extraction and answer generation. Each can independently use:

- **Local Qwen 2.5 · 3B** through Ollama
- **Groq Qwen 3.8 · 27B** through the Groq API

To enable Groq, create an API key in your Groq account, put it in `GROQ_API_KEY` in `apps/api/.env`, and restart the API. The key belongs only on the backend; never add it to `web/.env.local` or a `NEXT_PUBLIC_...` variable. If Groq is selected without a configured key, the request returns a configuration error. Ollama is still required for `nomic-embed-text` embeddings, and for each selector left on local Qwen.

### Quick troubleshooting

- **Web cannot reach the API:** confirm the API is running on port 8000 and `CONTRACT_API_URL` is correct.
- **Supabase URL/key error:** check the project URL and key; use the publishable/anon key in the web file and the secret/service-role key only in the API file.
- **Ollama connection/model error:** make sure Ollama is running and `ollama list` shows both models.
- **PowerShell says `npm` or `py` is not recognized:** reopen the terminal after installing Node.js or Python and verify that each was added to PATH.
- **Sign-up asks for email verification:** disable email confirmation in the Supabase Auth settings for this project.

## Project overview

### Goal

The research goal is to make contract question answering more reliable by representing contract structure, facts, evidence locations, and links between provisions. Retrieval can then use those signals to find supporting contract text and generate an answer with citations. The longer-term evaluation compares this approach with ordinary vector-search RAG.

### Current processing flow

```text
PDF upload
   ↓
Docling parses document structure and text
   ↓
Document chunks retain headings, page numbers, and source provenance
   ↓
Optional semantic extraction with Qwen or Groq
   ↓
Reference resolution creates links between provisions
   ↓
Question → retrieve relevant evidence → answer with citations
```

The workspace shows the PDF beside a single contract chat. The document and chat share the available workspace, with the chat history scrolling inside its pane. The chat offers two independent model selectors: one for semantic extraction and one for answer generation. The relationship-graph toggle is off by default. With it off, retrieval runs directly over Docling chunks and skips semantic extraction and graph construction. With it on, semantic extraction runs (or uses a compatible semantic cache), internal references are resolved, and graph links can add related chunks to retrieved evidence. The standard character-based naive RAG comparison is research scope and is not shown in the main chat UI.

### Main components

- **Docling** parses the PDF and provides document structure and provenance.
- **Qwen 2.5 · 3B through Ollama** can extract parties, definitions, obligations, rights, and references from chunks and generate answers.
- **Groq Qwen 3.8 · 27B** is an optional hosted choice for semantic extraction and/or answers. The extraction and answer choices are configured independently in chat.
- **Ollama `nomic-embed-text`** creates embeddings for vector retrieval.
- **Vector retrieval** ranks parsed chunks using cosine similarity over cached embeddings. Graph mode can expand the initial vector results with chunks connected by resolved contract references.
- **Local caches** store parsed documents, semantic results, and embeddings on the API machine.
- **Supabase Auth** provides web sign-in. The API is local and is not independently authenticated in this MVP.

The selected answer model is returned with each answer. The semantic model is used only when graph mode is enabled and semantic extraction is needed; changing it can produce a cache miss and make that processing run slower.

### API routes

- `POST /ask-contract` — retrieve contract evidence and answer a question.
- `GET /health` and `GET /health/supabase` — basic service checks.
- `/debug/*` — development endpoints for parsing, chunking, extraction, and retrieval. These are for local development, not a secured public deployment.

## Cache and refresh behavior

The API stores caches under `apps/api/.cache/`:

- `docling/` — parsed document output
- `semantic/` — semantic extraction results
- `embeddings/` — embedding vectors

Semantic cache entries are tied to the relevant input and extraction model, so changing the model or model version should cause a cache miss. Use the API’s force-refresh option when you need to rerun processing despite an existing compatible cache. These caches are machine-local and are not shared between users or deployments.

## Repository layout

```text
apps/api/     FastAPI service, document processing, extraction, retrieval, local caches
web/          Next.js application and Supabase sign-in
```

Useful commands:

```powershell
# API, from apps/api with its virtual environment active
uvicorn app.main:app --reload --port 8000

# Web, from web
npm run dev
npm run build
npm run lint
```

## Current scope and next research steps

The MVP supports PDF upload, contract questions, evidence-based answers, optional semantic processing, and reference-aware retrieval. Further work can improve reference resolution, evaluate how semantics and links affect answer quality, and build a controlled comparison against character-chunk vector RAG. The baseline comparison is for research rather than part of the professor-facing chat interface.
