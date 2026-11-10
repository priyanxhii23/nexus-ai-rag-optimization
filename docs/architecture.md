# NEXUS AI — Architecture

## One-sentence summary
NEXUS AI answers questions about your documents (RAG), but before paying for an
LLM call it checks whether a *similar enough* question was already answered for
the *same documents* (semantic cache), and when it must call an LLM it picks the
cheapest model that can handle the question (model routing). Every step is
measured so savings are proven, not claimed.

## Layers

```
┌──────────────────────────── FRONTEND (React + TS + Vite) ────────────────────────────┐
│ Overview · Playground · Documents · Cache · Router · Compare · Cost · Bench · Monitor │
└──────────────────────────────────────┬───────────────────────────────────────────────┘
                                       │ HTTP/JSON (+ SSE for streaming / live events)
┌──────────────────────────── BACKEND API (FastAPI) ────────────────────────────────────┐
│  api/  → thin route handlers, validation via Pydantic schemas                          │
│  services/ → orchestrates the pipeline below                                           │
└───────┬──────────────┬───────────────┬──────────────┬──────────────┬──────────────────┘
        │              │               │              │              │
  embeddings/      cache/          rag/          router/          llm/
  MiniLM model   semantic cache   chunk+retrieve  classify query   provider adapters
                 (Chroma coll.)   (Chroma coll.)  pick model       Claude · Gemini · OpenAI-compatible
        │              │               │              │              │
        └──────────────┴───────┬───────┴──────────────┴──────────────┘
                               │
                 analytics/ + evaluation/  (every event logged; benchmarks)
                               │
              ┌────────────────┴────────────────┐
              │ SQLite (SQLAlchemy)             │  ChromaDB (vectors)
              │ documents, versions, requests,  │  doc_chunks collection
              │ llm_calls, cache_meta, bench    │  query_cache collection
              └─────────────────────────────────┘
```

## Request flow
1. **Preprocess** – trim, normalise whitespace, validate length.
2. **Embed** – query → 384-number vector (all-MiniLM-L6-v2).
3. **Cache lookup** – search `query_cache`, filtered by tenant and by a
   *context fingerprint* (hash of the selected document IDs + their versions).
   - exact text match → exact hit
   - cosine similarity ≥ threshold → semantic hit
   - otherwise → miss
4. **On hit** – validate entry is not expired / invalidated → return it.
5. **On miss** – retrieve top-k chunks from `doc_chunks` → analyse query
   (intent, complexity) → router picks model → LLM generates answer with
   citations → store in cache → log tokens, latency, cost.

## Key design decisions (be ready to explain these in interviews)
| Decision | Why |
|---|---|
| Cache key includes document versions | Editing a PDF must not return answers based on the old PDF. |
| `tenant_id` on every row even with one user | Cache can never leak one user's private-doc answers to another. |
| Retrieved text placed in a *user-message data block*, never the system prompt | Basic prompt-injection defence. |
| Provider adapter interface | Swap/add LLMs without touching routing or caching code. |
| Pricing in a config file, not code | Prices change; costs are labelled *estimated* unless the provider returns usage. |
| Mock LLM mode | Tests and UI work without paid calls; mock answers are always labelled. |
