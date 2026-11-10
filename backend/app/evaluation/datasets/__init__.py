"""Reproducible evaluation datasets shipped with the code."""
import json
from pathlib import Path

DATASET_DIR = Path(__file__).parent


def list_datasets() -> list[dict]:
    out = []
    for p in sorted(DATASET_DIR.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out.append({"id": d["id"], "name": d["name"], "description": d["description"],
                    "documents": len(d["documents"]), "questions": len(d["questions"]), "pairs": len(d["pairs"])})
    return out


def load_dataset(dataset_id: str) -> dict:
    for p in DATASET_DIR.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d["id"] == dataset_id:
            return d
    raise KeyError(dataset_id)
