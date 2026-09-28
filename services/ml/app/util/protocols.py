"""Loads the fixed protocol JSON (services/ml/app/protocols/**) used by
followup and first_aid. The LLM never authors this content (technical.md
§9.7, §9.8) -- these loaders are the only path to it."""

import json
from functools import lru_cache
from pathlib import Path

PROTOCOLS_DIR = Path(__file__).parent.parent / "protocols"


@lru_cache
def load_followup_tree(facility: str) -> dict | None:
    path = PROTOCOLS_DIR / "followup" / f"{facility}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def load_all_first_aid() -> list[dict]:
    directory = PROTOCOLS_DIR / "first_aid"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]
