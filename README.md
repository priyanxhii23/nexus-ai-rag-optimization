# NEXUS AI
**Intelligent RAG Optimization & Cost-Aware Model Orchestration Platform**

> 🚧 Under active development — see [DEVELOPMENT_CHECKLIST.md](DEVELOPMENT_CHECKLIST.md) for progress.
> Every metric shown in this README will come from measured benchmark runs; none are filled in until they are measured.

## Problem
Teams that build document Q&A on LLMs pay for the same (or nearly the same) question
again and again, and often send simple questions to expensive models.

## Solution
NEXUS AI combines Retrieval-Augmented Generation with a **context-aware semantic cache**
and a **cost-aware model router**, then measures latency, cost and answer quality against
a plain-RAG baseline.

## Architecture
See [docs/architecture.md](docs/architecture.md).

## Tech stack
FastAPI · SQLAlchemy · SQLite · ChromaDB · sentence-transformers (all-MiniLM-L6-v2) ·
React · TypeScript · Vite · Tailwind CSS · Framer Motion · Recharts ·
Anthropic Claude · Google Gemini · OpenAI-compatible adapter

## Quick start
_Filled in at Milestone 2–3._

## Evaluation methodology & results
_Filled in at Milestone 8 from real benchmark runs._

## Limitations & future work
_Filled in at Milestone 10._
