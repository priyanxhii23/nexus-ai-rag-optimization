"""One-time / repeatable initialisation, called by setup_windows.ps1.

  python scripts/init_app.py                   # validate config, create folders, create/upgrade the database
  python scripts/init_app.py --download-model  # also download the embedding model (~90 MB, once)

Safe to run many times: it only CREATES or UPGRADES things and never deletes data.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialise NEXUS AI")
    parser.add_argument("--download-model", action="store_true", help="Download the sentence-transformers model now")
    args = parser.parse_args()

    # 1. configuration
    try:
        from app.core.config import PROJECT_ROOT, get_settings
        s = get_settings()
    except Exception as exc:  # pydantic ValidationError, bad .env value
        print(f"[ERROR] Configuration in .env is invalid:\n{exc}")
        print("        Fix the value named above in your .env file and run setup again.")
        return 1
    print(f"[OK] Configuration loaded (APP_ENV={s.app_env})")
    if not (PROJECT_ROOT / ".env").exists():
        print("[WARN] No .env file found - using defaults.")

    # 2. folders
    s.ensure_directories()
    print("[OK] Data folders ready (data/documents, data/chroma, data/models, data/logs, data/benchmarks)")

    # 3. database (create tables / add new columns to an older database)
    from app.database import SessionLocal, configure_engine, init_db
    from app.llm.registry import seed_models
    init_db(configure_engine())
    db = SessionLocal()
    try:
        seed_models(db, s)
    finally:
        db.close()
    print(f"[OK] Database ready: {s.resolve(s.sqlite_path)}")

    # 4. providers (never print key values)
    configured = [k for k, v in s.provider_status.items() if v]
    if s.mock_mode:
        print("[INFO] TEST MODE: no LLM provider configured (or LLM_MOCK_MODE=true).")
        print("       Answers will be clearly labelled mock output. Add ANTHROPIC_API_KEY or GEMINI_API_KEY to .env for real LLMs.")
    else:
        print(f"[OK] LLM providers configured: {', '.join(configured)}")
    if s.gemini_api_key and not (s.gemini_small_model or s.gemini_large_model):
        print("[INFO] GEMINI_API_KEY is set but no Gemini model is chosen yet: set GEMINI_SMALL_MODEL / GEMINI_LARGE_MODEL")
        print("       in .env, or add a model in Settings -> LLM providers (the list comes from Google's API).")

    # 5. embedding model
    if args.download_model:
        os.environ.setdefault("HF_HOME", str(s.resolve(s.models_cache_path)))
        print(f"[...] Downloading / loading embedding model '{s.embedding_model}' (first time ~90 MB) ...")
        try:
            from app.embeddings import SentenceTransformerEmbedder
            emb = SentenceTransformerEmbedder(s.embedding_model, str(s.resolve(s.models_cache_path)))
            vec = emb.embed(["NEXUS AI setup check"])[0]
            print(f"[OK] Embedding model works (vector size = {len(vec)})")
        except Exception as exc:
            print(f"[ERROR] Could not load the embedding model: {type(exc).__name__}: {exc}")
            print("        Check your internet connection (huggingface.co must be reachable) and run setup again.")
            return 2

    print("[DONE] Initialisation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
