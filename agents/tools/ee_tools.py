"""
Earth Engine Tools

Shared tools for Researcher and Coder agents to query Earth Engine
for real-time dataset information, metadata, and schema discovery.
"""

import ee
from typing import Any, Optional
from functools import lru_cache


import os

def initialize_ee() -> bool:
    """Initialize Earth Engine. Returns True if successful."""
    try:
        project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("EE_PROJECT_ID")
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        return True
    except Exception:
        try:
            ee.Authenticate()
            if project:
                ee.Initialize(project=project)
            else:
                ee.Initialize()
            return True
        except Exception as e:
            print(f"Failed to initialize Earth Engine: {e}")
            return False


@lru_cache(maxsize=100)
def browse_datasets(query: str) -> list[dict]:
    """
    Search for datasets matching keywords.
    
    Args:
        query: Search keywords (e.g., "landsat ndvi vegetation")
    
    Returns:
        List of matching dataset info dicts
    """
    # Common dataset mappings for quick lookup
    DATASET_KEYWORDS = {
        "landsat": [
            {"id": "LANDSAT/LC09/C02/T1_L2", "name": "Landsat 9 Level 2", "type": "optical"},
            {"id": "LANDSAT/LC08/C02/T1_L2", "name": "Landsat 8 Level 2", "type": "optical"},
            {"id": "LANDSAT/LE07/C02/T1_L2", "name": "Landsat 7 Level 2", "type": "optical"},
        ],
        "sentinel": [
            {"id": "COPERNICUS/S2_SR_HARMONIZED", "name": "Sentinel-2 Surface Reflectance", "type": "optical"},
            {"id": "COPERNICUS/S1_GRD", "name": "Sentinel-1 SAR GRD", "type": "sar"},
            {"id": "COPERNICUS/S5P/OFFL/L3_NO2", "name": "Sentinel-5P NO2", "type": "atmosphere"},
        ],
        "modis": [
            {"id": "MODIS/061/MOD13A1", "name": "MODIS Vegetation Indices", "type": "vegetation"},
            {"id": "MODIS/061/MOD09GA", "name": "MODIS Surface Reflectance", "type": "optical"},
            {"id": "MODIS/061/MCD12Q1", "name": "MODIS Land Cover", "type": "landcover"},
        ],
        "climate": [
            {"id": "ECMWF/ERA5_LAND/DAILY_AGGR", "name": "ERA5-Land Daily", "type": "climate"},
            {"id": "UCSB-CHG/CHIRPS/DAILY", "name": "CHIRPS Precipitation", "type": "precipitation"},
        ],
        "elevation": [
            {"id": "USGS/SRTMGL1_003", "name": "SRTM Digital Elevation", "type": "elevation"},
            {"id": "JAXA/ALOS/AW3D30/V3_2", "name": "ALOS World 3D", "type": "elevation"},
        ],
        "ndvi": [
            {"id": "MODIS/061/MOD13A1", "name": "MODIS NDVI/EVI", "type": "vegetation"},
            {"id": "LANDSAT/LC09/C02/T1_L2", "name": "Landsat 9 (compute NDVI)", "type": "optical"},
        ],
        "sar": [
            {"id": "COPERNICUS/S1_GRD", "name": "Sentinel-1 SAR", "type": "sar"},
        ],
        "flood": [
            {"id": "COPERNICUS/S1_GRD", "name": "Sentinel-1 SAR (flood detection)", "type": "sar"},
            {"id": "JRC/GSW1_4/GlobalSurfaceWater", "name": "Global Surface Water", "type": "water"},
        ],
        "fire": [
            {"id": "MODIS/061/MOD14A1", "name": "MODIS Thermal Anomalies/Fire", "type": "fire"},
            {"id": "FIRMS", "name": "FIRMS Active Fires", "type": "fire"},
        ],
        "deforestation": [
            {"id": "UMD/hansen/global_forest_change_2023_v1_11", "name": "Hansen Global Forest Change", "type": "forest"},
            {"id": "LANDSAT/LC09/C02/T1_L2", "name": "Landsat 9 (forest analysis)", "type": "optical"},
        ],
    }
    
    results = []
    query_lower = query.lower()
    
    for keyword, datasets in DATASET_KEYWORDS.items():
        if keyword in query_lower:
            results.extend(datasets)
    
    # Remove duplicates
    seen_ids = set()
    unique_results = []
    for d in results:
        if d["id"] not in seen_ids:
            seen_ids.add(d["id"])
            unique_results.append(d)
    
    return unique_results if unique_results else [
        {"id": "COPERNICUS/S2_SR_HARMONIZED", "name": "Sentinel-2 (default)", "type": "optical"}
    ]


def get_asset_metadata(asset_id: str) -> dict:
    """
    Get full metadata for an Earth Engine asset.
    
    Args:
        asset_id: Earth Engine asset ID (e.g., "LANDSAT/LC09/C02/T1_L2")
    
    Returns:
        Asset metadata dict
    """
    try:
        if not initialize_ee():
            return {"error": "Failed to initialize Earth Engine"}
        
        # Try as image collection first
        try:
            collection = ee.ImageCollection(asset_id)
            info = collection.first().getInfo()
            size = collection.size().getInfo()
            return {
                "id": asset_id,
                "type": "ImageCollection",
                "size": size,
                "bands": [{"name": b["id"], "type": b.get("data_type", {}).get("type", "unknown")} 
                         for b in info.get("bands", [])],
                "properties": list(info.get("properties", {}).keys())[:20],
                "sample_properties": {k: v for k, v in list(info.get("properties", {}).items())[:10]}
            }
        except:
            # Try as single image
            image = ee.Image(asset_id)
            info = image.getInfo()
            return {
                "id": asset_id,
                "type": "Image",
                "bands": [{"name": b["id"], "type": b.get("data_type", {}).get("type", "unknown")} 
                         for b in info.get("bands", [])],
                "properties": list(info.get("properties", {}).keys())[:20]
            }
    except Exception as e:
        return {"error": str(e), "id": asset_id}


def get_band_schema(collection_id: str) -> dict:
    """
    Get band names, types, and scales for a collection.
    Critical for Coder to generate correct band references.
    
    Args:
        collection_id: Earth Engine collection ID
    
    Returns:
        Schema dict with band info
    """
    try:
        if not initialize_ee():
            return {"error": "Failed to initialize Earth Engine"}
        
        collection = ee.ImageCollection(collection_id)
        sample = collection.first()
        info = sample.getInfo()
        
        bands = []
        for b in info.get("bands", []):
            band_info = {
                "name": b["id"],
                "data_type": b.get("data_type", {}).get("type", "unknown"),
            }
            if "crs" in b:
                band_info["crs"] = b["crs"]
            if "dimensions" in b:
                band_info["dimensions"] = b["dimensions"]
            bands.append(band_info)
        
        return {
            "collection_id": collection_id,
            "bands": bands,
            "band_names": [b["name"] for b in bands],
            "properties": list(info.get("properties", {}).keys())[:30]
        }
    except Exception as e:
        return {"error": str(e), "collection_id": collection_id}


def preview_collection(
    collection_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5
) -> dict:
    """
    Preview available images in a collection.
    
    Args:
        collection_id: Earth Engine collection ID
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        limit: Max images to return info for
    
    Returns:
        Preview info dict
    """
    try:
        if not initialize_ee():
            return {"error": "Failed to initialize Earth Engine"}
        
        collection = ee.ImageCollection(collection_id)
        
        if start_date and end_date:
            collection = collection.filterDate(start_date, end_date)
        
        count = collection.size().getInfo()
        
        # Get sample image info
        samples = collection.limit(limit).getInfo()
        
        image_previews = []
        for feat in samples.get("features", []):
            props = feat.get("properties", {})
            image_previews.append({
                "id": feat.get("id", "unknown"),
                "date": props.get("system:time_start", props.get("DATE_ACQUIRED", "unknown")),
                "cloud_cover": props.get("CLOUD_COVER", props.get("CLOUDY_PIXEL_PERCENTAGE", "N/A"))
            })
        
        return {
            "collection_id": collection_id,
            "total_images": count,
            "date_range": f"{start_date} to {end_date}" if start_date else "all dates",
            "sample_images": image_previews
        }
    except Exception as e:
        return {"error": str(e), "collection_id": collection_id}


def get_dataset_docs(asset_id: str) -> str:
    """
    Get documentation URL and description for a dataset.
    
    Args:
        asset_id: Earth Engine asset ID
    
    Returns:
        Documentation string
    """
    # Dataset documentation URLs
    DOCS = {
        "LANDSAT/LC09/C02/T1_L2": "https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2",
        "LANDSAT/LC08/C02/T1_L2": "https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2",
        "COPERNICUS/S2_SR_HARMONIZED": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
        "COPERNICUS/S1_GRD": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD",
        "MODIS/061/MOD13A1": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A1",
    }
    
    base_url = "https://developers.google.com/earth-engine/datasets/catalog/"
    catalog_id = asset_id.replace("/", "_")
    
    return DOCS.get(asset_id, f"{base_url}{catalog_id}")


# Tool definitions for LangChain
EE_TOOLS = [
    {
        "name": "browse_datasets",
        "description": "Search for Earth Engine datasets matching keywords. Returns dataset IDs and types.",
        "function": browse_datasets
    },
    {
        "name": "get_asset_metadata", 
        "description": "Get full metadata for an Earth Engine asset including bands and properties.",
        "function": get_asset_metadata
    },
    {
        "name": "get_band_schema",
        "description": "Get band names, types for a collection. Use before generating code to get correct band names.",
        "function": get_band_schema
    },
    {
        "name": "preview_collection",
        "description": "Preview available images in a collection for a date range. Check data availability.",
        "function": preview_collection
    },
    {
        "name": "get_dataset_docs",
        "description": "Get documentation URL for a dataset.",
        "function": get_dataset_docs
    }
]
