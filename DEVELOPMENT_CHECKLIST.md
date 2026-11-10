# NEXUS AI - Development Checklist (v0.4.0)

Legend: [x] implemented **and** tested · [~] implemented, not yet verified where noted · [ ] not done

"Tested" below means: executed in the cloud development container (Linux, Python 3.12, Node 22,
PowerShell 7.6, headless Chromium). **Nothing has been run on the Windows laptop yet.**

## Audit of the uploaded v3.1 code
- [x] Full audit with severities → `docs/AUDIT_REPORT.md` (21 findings; all addressed below)

## Backend foundation
- [x] FastAPI app, lifespan startup/shutdown, Swagger at /docs
- [x] Settings from .env with validation; placeholder keys treated as missing
- [x] SQLite + SQLAlchemy, lazy engine, WAL, foreign keys, timezone-aware timestamps
- [x] Additive migrations: a real v3.1 `nexus.db` is upgraded without data loss (tested)
- [x] Tests use a throw-away database (the real `data/nexus.db` is never touched)
- [x] Central error handling (one JSON error shape, request IDs), rotating log file
- [x] CORS for localhost + 127.0.0.1, security headers, rate limiting, request-size limit

## Features
- [x] 1 Multi-document RAG (PDF/TXT/MD, chunking, embeddings, ChromaDB, citations, update, delete, duplicates)
- [x] 2 Semantic cache (exact + cosine, threshold, TTL, invalidation, tenant/scope isolation, intent guard)
- [x] 3 Model routing (3 strategies, manual, nearest tier, fallback chain)
- [x] 4 Threshold optimizer (real-embedding measurement, safety-first recommendation)
- [x] 5 Model comparison (identical context, parallel, metrics, Markdown report)
- [x] 6 Cost intelligence (provider/estimated tokens, priced/simulated/unpriced, counterfactual savings)
- [x] 7 Cache management UI (search, filter, inspect, delete, clear, settings)
- [x] 8 Query intelligence (6 categories, complexity score, signals)
- [x] 9 Benchmarking lab (A/B/C, isolated tenant, all required metrics, MD/CSV reports)
- [x] 10 Live monitoring (event stream with polling, stats, service status)
- [x] Settings (runtime settings in DB, model enable/disable, prices, Gemini/compat model discovery)

## LLM providers
- [x] Mock provider (labelled, extractive, deterministic) - used by all tests
- [x] Anthropic adapter - tested with a fake SDK client (usage, effort, server-side fallback, refusal)
- [x] Gemini adapter - tested with a fake SDK client (usage incl. thinking tokens)
- [x] OpenAI-compatible adapter - tested with a fake SDK client (reported + estimated usage)
- [~] **Real API calls have NOT been made** (no keys in the dev container). First real call happens on your laptop.

## Frontend
- [x] React + TS + Vite + Tailwind v4 + Framer Motion + Recharts + Lucide; all 10 pages functional
- [x] Light/dark themes (persisted, no flash), reduced-motion toggle, responsive (phone drawer)
- [x] TypeScript compile, production build (code-split), 17 Vitest tests
- [x] Browser check: all 10 pages × 2 themes, zero console errors, no horizontal scroll at 390 px

## Windows
- [x] setup_windows.ps1 / start_backend.ps1 / start_frontend.ps1 / helper scripts executed with PowerShell 7 on Linux
- [~] start_all.bat / stop_all.bat / SETUP.bat / START.bat - **not executable in the container (no cmd.exe)**; reviewed only
- [ ] Verified on the Windows laptop (Windows PowerShell 5.1, `py` launcher, taskkill)

## Open items
- [ ] Run with real Claude / Gemini keys and record a real (non-simulated) benchmark
- [ ] Enter Gemini prices from https://ai.google.dev/gemini-api/docs/pricing (not pre-filled on purpose)
- [ ] Screenshots for the README taken on the laptop
- [ ] Push to GitHub (only after your approval)
