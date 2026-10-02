# LexGraph web

Next.js frontend for the contract question-answering demo.

## Setup

1. Copy `.env.example` to `.env.local`.
2. Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` from the Supabase project settings. These are the browser-safe project URL and publishable/anon key; do not put a service-role or secret key in this frontend.
3. Set `CONTRACT_API_URL` to the FastAPI origin (defaults to `http://localhost:8000`).
4. To enable the Groq choices, add `GROQ_API_KEY` to `apps/api/.env`. The key stays on the API server. Start the API and Ollama, then start the frontend with `npm run dev`.

Supabase Auth is used for sign-in and sign-up. The workspace keeps the selected PDF and chat in browser memory for the current session; it does not create application tables or upload documents to Supabase Storage.

The workspace uses the single-answer `/ask-contract` API route. Choose local Qwen or Groq Qwen separately for semantic extraction and answer generation. Its retrieval switch is off by default: this retrieves directly from Docling chunks and skips semantic extraction and graph construction. Turn it on to use semantic extraction and graph-assisted retrieval; the first run can take longer. The research-only `/debug/retrieve-contract` route remains available for comparing vector and graph-assisted retrieval outside the main UI.

The API itself is not authenticated in this MVP. Keep it on a trusted local network and do not expose the API publicly.
