"""
STAC-backed dataset schema tools for the Coder agent.

Provides deterministic, ground-truth knowledge of EE dataset band names, scales,
and date ranges sourced from the EE STAC catalog (built by scripts/build_stac_index.py).
Falls back to a lightweight online fetch when the local index is missing.

Exports:
    get_dataset_schema(dataset_id)  — look up a dataset by EE ID
    GET_DATASET_SCHEMA_DECL         — Gemini function declaration
    ANTHROPIC_GET_DATASET_SCHEMA    — Anthropic tool schema
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

INDEX_PATH = Path(__file__).parent.parent / "data" / "ee_stac_index.json"

# ---------------------------------------------------------------------------
# Index loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_index() -> dict:
    """Load the STAC index from disk; return empty dict if not built yet."""
    if not INDEX_PATH.exists():
        return {}
    return json.loads(INDEX_PATH.read_text())


def _normalise_id(dataset_id: str) -> str:
    """Normalise dataset IDs: strip leading/trailing slashes, upper-case."""
    return dataset_id.strip("/").strip()


def _find_record(dataset_id: str) -> Optional[dict]:
    """
    Look up a dataset record, trying several normalisation variants.

    Handles:
      - Exact match                      COPERNICUS/S2_SR_HARMONIZED
      - Case-insensitive match
      - Underscore ↔ slash variants      COPERNICUS_S2_SR_HARMONIZED
    """
    index = _load_index()
    if not index:
        return None

    normalised = _normalise_id(dataset_id)

    # 1. Exact match
    if normalised in index:
        return index[normalised]

    # 2. Case-insensitive scan (index is small enough)
    lower = normalised.lower()
    for key, rec in index.items():
        if key.lower() == lower:
            return rec

    # 3. Underscore → slash variant (users sometimes write COPERNICUS_S2_…)
    slash_variant = normalised.replace("_", "/")
    if slash_variant in index:
        return index[slash_variant]
    # And the reverse
    underscore_variant = normalised.replace("/", "_")
    for key, rec in index.items():
        if key.replace("/", "_").lower() == underscore_variant.lower():
            return rec

    return None


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------

def get_dataset_schema(dataset_id: str) -> dict:
    """
    Return structured schema information for an Earth Engine dataset.

    Args:
        dataset_id: EE dataset ID (e.g. "COPERNICUS/S2_SR_HARMONIZED")

    Returns:
        {
            "id": str,
            "title": str,
            "gee_type": str,
            "bands": [{"name", "description", "scale", "gsd", "center_wavelength"}],
            "scale_factors": {band_name: scale},
            "date_range": {"start": str, "end": str},
            "spatial_extent": [west, south, east, north],
            "schema_properties": [{"name", "type", "description"}],
            "provider": str,
        }

    Raises:
        ValueError if dataset not found in the index and online fetch fails.
    """
    record = _find_record(dataset_id)

    if record is None:
        # Index not built yet or dataset not found — attempt a lightweight online fetch
        record = _fetch_stac_record(dataset_id)

    if record is None:
        raise ValueError(
            f"Dataset {dataset_id!r} not found in STAC index. "
            "Run `python scripts/build_stac_index.py` to build the index, "
            "or verify the dataset ID at https://developers.google.com/earth-engine/datasets"
        )

    bands = record.get("bands", [])
    scale_factors = {
        b["name"]: b["scale"]
        for b in bands
        if b.get("scale") is not None
    }

    return {
        "id": record["id"],
        "title": record.get("title", ""),
        "gee_type": record.get("gee_type", ""),
        "bands": bands,
        "scale_factors": scale_factors,
        "date_range": {
            "start": record.get("date_start"),
            "end": record.get("date_end"),
        },
        "spatial_extent": record.get("spatial_bbox", []),
        "schema_properties": record.get("schema_properties", []),
        "provider": record.get("provider_name", ""),
    }


# ---------------------------------------------------------------------------
# Online fallback (when index not yet built)
# ---------------------------------------------------------------------------

def _fetch_stac_record(dataset_id: str) -> Optional[dict]:
    """Try to fetch a single dataset from the EE STAC online catalog."""
    try:
        import httpx
        # EE STAC path convention: COPERNICUS/S2_SR_HARMONIZED → COPERNICUS/COPERNICUS_S2_SR_HARMONIZED.json
        parts = dataset_id.strip("/").split("/")
        namespace = parts[0]
        slug = "_".join(parts)
        url = (
            f"https://storage.googleapis.com/earthengine-stac/catalog/"
            f"{namespace}/{slug}.json"
        )
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return None
        data = resp.json()
        # Reuse the same extraction logic as the builder
        from scripts.build_stac_index import extract_dataset
        return extract_dataset(data)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Function declarations (for tool-calling)
# ---------------------------------------------------------------------------

# Gemini function declaration (google.genai types.FunctionDeclaration format)
GET_DATASET_SCHEMA_DECL = {
    "name": "get_dataset_schema",
    "description": (
        "Look up the band names, scale factors, date range, and spatial extent "
        "for a Google Earth Engine dataset by its EE ID. Always call this before "
        "referencing any band name in generated code to avoid hallucination."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": (
                    "The Earth Engine dataset ID, e.g. 'COPERNICUS/S2_SR_HARMONIZED' "
                    "or 'LANDSAT/LC09/C02/T1_L2'."
                ),
            }
        },
        "required": ["dataset_id"],
    },
}

# Anthropic tool schema (claude tool_use format)
ANTHROPIC_GET_DATASET_SCHEMA = {
    "name": "get_dataset_schema",
    "description": GET_DATASET_SCHEMA_DECL["description"],
    "input_schema": {
        "type": "object",
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": GET_DATASET_SCHEMA_DECL["parameters"]["properties"]["dataset_id"]["description"],
            }
        },
        "required": ["dataset_id"],
    },
}

# OpenAI / LiteLLM function-calling format (LiteLLM converts to Anthropic tool_use)
LITELLM_GET_DATASET_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_dataset_schema",
        "description": GET_DATASET_SCHEMA_DECL["description"],
        "parameters": GET_DATASET_SCHEMA_DECL["parameters"],
    },
}

# Dispatch map: tool name → callable (used by the Coder's tool loop)
STAC_TOOL_DISPATCH: dict = {
    "get_dataset_schema": get_dataset_schema,
}
