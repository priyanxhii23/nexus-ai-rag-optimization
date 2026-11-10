# NEXUS AI v3.1 — Code Audit Report

Audited: the uploaded `nexus-ai-v3.1.zip` (54 files). Every Python, TypeScript/TSX,
JSON, config, script and test file was read. In addition, the code was **executed** in
a Linux cloud container (Python 3.12, Node 22, PowerShell 7, headless Chromium):

| Check actually executed | Result |
|---|---|
| `pytest` (backend, 6 tests) | 6 passed |
| `uvicorn app.main:app` + `GET /api/health` | 200 OK, DB check real |
| CORS pre-flight from `http://127.0.0.1:5173` | **400** (only `localhost` origin allowed) |
| `npm ci` → `npm run build` (tsc + vite) | success, no TypeScript errors |
| `npm run lint` (oxlint) | 2 warnings |
| Browser render: Overview, Settings, placeholder pages, 404, theme toggle | renders, **no console errors** |
| Browser render at phone width (390 px) | **layout broken** (sidebar takes 232 of 390 px) |
| `.env.example` copied to `.env` → settings parse | values parse correctly (inline comments OK) |
| Running the test suite | **creates/writes the real `data/nexus.db`** |

Not executed: the Windows `.bat`/`.ps1` scripts on real Windows (no Windows machine available).

## Summary

The v3.1 code that exists is **clean and runs**: backend foundation (Milestone 2) and the
dashboard shell (Milestone 3) work. But the product described in the requirements is
mostly **not implemented yet**: there is no RAG, no embeddings, no vector store, no
semantic cache, no router, no LLM providers, no cost tracking, no benchmarking, and
8 of 10 pages are placeholders. That is expected for the milestone it is at, not a bug,
but it means "complete" is far away.

## Findings

Severity: **Critical** = a required feature is missing or data can be damaged ·
**High** = breaks a requirement or will break soon · **Medium** = wrong/misleading
behaviour · **Low** = quality / polish.

| # | Severity | Area | Finding | Evidence |
|---|---|---|---|---|
| 1 | Critical | Features | Features 1–10 (RAG, semantic cache, routing, query intelligence, cost, comparison, benchmarking, monitoring, cache management, settings editing) are not implemented. Only `/api/health` and `/api/metrics/overview` exist. | `backend/app/api/` has 2 routers; `Upcoming.tsx` used for 8 pages |
| 2 | Critical | Dependencies | `requirements.txt` lacks sentence-transformers, chromadb, pypdf, numpy and the Anthropic / Gemini / OpenAI SDKs. | `backend/requirements.txt` line 13 |
| 3 | High | Tests / data integrity | Tests override `get_db`, but `TestClient(app)` still runs the app *lifespan*, whose `init_db()` uses the global engine → running tests creates/modifies your **real** `data/nexus.db`. | executed: `data/nexus.db` appeared after `pytest` |
| 4 | High | Database | Schema management is `create_all()` only. It never adds new columns to existing tables, so the first schema change will crash an existing `nexus.db` (“no such column”). | `database/__init__.py` `init_db` |
| 5 | High | Windows scripts | Requested `setup_windows.ps1`, `start_all.bat`, `stop_all.bat` do not exist. There is no way to stop the servers except closing windows. | file list |
| 6 | High | Frontend / responsive | The sidebar is always 232 px wide; at phone width the content column is ~150 px and text wraps word-by-word. | executed: screenshot at 390 px |
| 7 | Medium | Config | `.env.example` ships `OPENAI_COMPAT_BASE_URL=http://localhost:11434/v1`, so after copying it the health check reports the OpenAI-compatible provider as **configured** even when no Ollama server exists. | `health.py` line 36 |
| 8 | Medium | Mock mode | `LLM_MOCK_MODE=false` by default and nothing decides what happens with *no* keys. Mock mode should switch on automatically (and visibly) when no provider is usable. | `config.py` |
| 9 | Medium | Error handling | No central exception handlers: unhandled errors return a bare `Internal Server Error`; validation errors use FastAPI's raw format; no request IDs. | `main.py` |
| 10 | Medium | Logging | Console only (`basicConfig`), no log file, no request logging/timing. | `core/logging.py` |
| 11 | Medium | Setup script | `scripts/setup.ps1` uses `$ErrorActionPreference='Continue'` and keeps going after `pip install` fails, so later steps fail with confusing errors. | lines 5, 60 |
| 12 | Medium | Start script | `start.ps1` only waits for the frontend, never checks the backend, does not detect busy ports, and opens a browser on a page that may show "Backend offline". | `scripts/start.ps1` |
| 13 | Medium | Proxy | Vite proxy targets `http://localhost:8000` while uvicorn binds `127.0.0.1`. On some Windows/Node setups `localhost` resolves to IPv6 `::1` first → intermittent `ECONNREFUSED`. | `vite.config.ts` |
| 14 | Medium | Timestamps | SQLite returns naive datetimes; `created_at.isoformat()` is sent without a timezone, so browsers treat UTC times as local time. | `metrics.py` line 62 |
| 15 | Medium | Security | No rate limiting, no request-size limit, no prompt-injection handling (no LLM yet, so not exploitable today). | — |
| 16 | Low | CORS | Only `http://localhost:5173` allowed; `http://127.0.0.1:5173` pre-flight returns 400. | executed |
| 17 | Low | Side effects | `app/database/__init__.py` creates folders and the engine at import time; tests cannot swap the database cleanly. | lines 25–28 |
| 18 | Low | Frontend tests | No frontend test runner or tests. | `package.json` |
| 19 | Low | Lint | `usePolling` writes a ref during render; `AnimatedNumber` calls setState synchronously in an effect. | `oxlint` output |
| 20 | Low | UX | The offline banner tells a Windows user to run `uvicorn app.main:app --reload` (wrong folder/venv). | `Overview.tsx` line 32 |
| 21 | Low | Polling | `usePolling` can overlap requests and set state after unmount. | `usePolling.ts` |

## What is good and is kept

* Project layout, `tenant_id` on every table, `usage_source` label on LLM calls,
  `has_data` honest empty states, design tokens for light/dark, theme persistence,
  reduced-motion support, provider keys never returned by the API, `.gitignore` coverage.

## Plan

All findings are addressed in the same order the brief asks for (backend → frontend →
integration → RAG → cache → routing/cost → benchmarking/comparison → monitoring/settings →
security/docs). The fixes are recorded in `DEVELOPMENT_CHECKLIST.md`.
