"""Shared FastAPI dependencies (singletons for the vector store, embedder and model registry)."""
from app.embeddings import Embedder, get_embedder
from app.llm.registry import ModelRegistry, get_registry
from app.rag.vector_store import VectorStore, get_vector_store


def store_dep() -> VectorStore:
    return get_vector_store()


def embedder_dep() -> Embedder:
    return get_embedder()


def registry_dep() -> ModelRegistry:
    return get_registry()
