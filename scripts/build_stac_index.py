"""
Build the Earth Engine STAC index.

Walks the EE STAC catalog tree starting from the root catalog.json, extracts
band schemas, temporal extents, spatial extents, and dataset properties, then
writes agents/data/ee_stac_index.json keyed by dataset ID for O(1) lookup.

EE STAC structure:
  Root Catalog → child sub-Catalogs → child Collection items (individual datasets)

Usage:
    python scripts/build_stac_index.py            # build full index
    python scripts/build_stac_index.py --dry-run  # fetch 5 datasets, print, no write
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx

STAC_ROOT = "https://storage.googleapis.com/earthengine-stac/catalog/catalog.json"
OUTPUT_PATH = Path(__file__).parent.parent / "agents" / "data" / "ee_stac_index.json"
REQUEST_DELAY = 0.05  # seconds between requests — polite to GCS


def fetch_json(url: str, client: httpx.Client, retries: int = 3) -> Optional[dict]:
    for attempt in range(retries):
        try:
            resp = client.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt == retries - 1:
                print(f"  ⚠ Failed to fetch {url}: {exc}", file=sys.stderr)
                return None
            time.sleep(1)
    return None


def _has_dataset_shape(data: dict) -> bool:
    """Return True if this STAC item looks like an EE dataset collection."""
    props = data.get("properties", {})
    summaries = data.get("summaries", {})
    return bool(
        data.get("id")
        and data.get("type") == "Collection"
        and (
            summaries.get("eo:bands")
            or props.get("gee:type")
            or data.get("extent")
        )
    )


def extract_dataset(item: dict) -> Optional[dict]:
    """Extract the fields we care about from a STAC Collection (EE dataset)."""
    dataset_id = item.get("id")
    if not dataset_id:
        return None

    props = item.get("properties", {})
    summaries = item.get("summaries", {})
    extent = item.get("extent", {})
    temporal = extent.get("temporal", {}).get("interval", [[None, None]])[0]
    spatial_bbox = extent.get("spatial", {}).get("bbox", [[]])[0]

    # Bands
    raw_bands = summaries.get("eo:bands", [])
    bands = [
        {
            "name": b.get("name", ""),
            "description": b.get("description", ""),
            "scale": b.get("gee:scale"),
            "gsd": b.get("gsd"),
            "center_wavelength": b.get("center_wavelength"),
        }
        for b in raw_bands
        if b.get("name")
    ]

    # Schema properties (for image property filtering)
    schema = [
        {
            "name": s.get("name", ""),
            "type": s.get("type", ""),
            "description": s.get("description", ""),
        }
        for s in item.get("gee:schema", [])
        if s.get("name")
    ]

    # Provider info
    providers = item.get("providers", [])
    provider = providers[0] if providers else {}

    return {
        "id": dataset_id,
        "title": props.get("title", "") or item.get("title", ""),
        "gee_type": props.get("gee:type", "") or summaries.get("gee:schema", [{}])[0].get("type", ""),
        "bands": bands,
        "schema_properties": schema,
        "date_start": temporal[0] if temporal else None,
        "date_end": temporal[1] if len(temporal) > 1 else None,
        "spatial_bbox": spatial_bbox,
        "provider_name": provider.get("name", ""),
        "links": {
            lk.get("rel"): lk.get("href")
            for lk in item.get("links", [])
            if lk.get("rel") in ("license", "source", "canonical", "self")
        },
    }


def walk_catalog(
    catalog_url: str,
    client: httpx.Client,
    dry_run: bool,
    visited: set,
    count: list,
) -> list[dict]:
    """Recursively walk a STAC catalog and return dataset records."""
    if catalog_url in visited:
        return []
    visited.add(catalog_url)

    if dry_run and count[0] >= 5:
        return []

    data = fetch_json(catalog_url, client)
    if not data:
        return []

    time.sleep(REQUEST_DELAY)
    records = []

    # If this node is a dataset Collection, extract it
    if _has_dataset_shape(data):
        record = extract_dataset(data)
        if record:
            records.append(record)
            count[0] += 1
            print(f"  [{count[0]:4d}] {record['id']} ({len(record['bands'])} bands)")
        return records

    # Otherwise it's a Catalog — walk child links
    base_parts = catalog_url.rsplit("/", 1)
    base = base_parts[0] + "/" if len(base_parts) > 1 else ""

    for link in data.get("links", []):
        rel = link.get("rel", "")
        href = link.get("href", "")
        if rel not in ("child", "item"):
            continue
        child_url = href if href.startswith("http") else urljoin(base, href)
        if child_url in visited:
            continue
        if dry_run and count[0] >= 5:
            break

        child_records = walk_catalog(child_url, client, dry_run, visited, count)
        records.extend(child_records)

    return records


def build_index(dry_run: bool = False) -> None:
    print(f"{'[DRY RUN] ' if dry_run else ''}Building EE STAC index from {STAC_ROOT}")

    visited: set = set()
    count = [0]  # mutable counter shared across recursive calls
    with httpx.Client(follow_redirects=True) as client:
        records = walk_catalog(STAC_ROOT, client, dry_run, visited, count)

    index = {r["id"]: r for r in records if r.get("id")}

    if dry_run:
        print(f"\nFetched {len(index)} datasets (dry run — not writing file):")
        for dataset_id, rec in list(index.items()):
            print(f"\n  {dataset_id}")
            print(f"    title:     {rec['title'][:60]}")
            print(f"    gee_type:  {rec['gee_type']}")
            print(f"    bands:     {[b['name'] for b in rec['bands'][:6]]}")
            print(f"    date:      {rec['date_start']} → {rec['date_end']}")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(index, indent=2))
    print(f"\n✅ Wrote {len(index)} datasets to {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build EE STAC index")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch 5 datasets and print without writing",
    )
    args = parser.parse_args()
    build_index(dry_run=args.dry_run)
