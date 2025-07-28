#!/usr/bin/env python3
import os
import logging
import json
import time
import asyncio

from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from geoalchemy2.functions import ST_Distance, ST_GeomFromGeoJSON, ST_AsGeoJSON
from shapely.geometry import shape
from pyproj import Transformer
from dotenv import load_dotenv

# Load .env in local dev; in Cloud Run env vars will come from the service config
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("uvp_backend")

# FastAPI app
app = FastAPI(title="GeoJSON Protected Areas Finder", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://clmns97.github.io"
    ],
    allow_credentials=True,
    allow_methods=["*"],    # <— allow all verbs, including OPTIONS
    allow_headers=["*"],    # <— allow any header
)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "user")
    pw   = os.getenv("POSTGRES_PASSWORD", "password")
    db   = os.getenv("POSTGRES_DB", "geoapp")
    DATABASE_URL = f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Pydantic models
class GeoJSONRequest(BaseModel):
    geojson: Dict[str, Any]

class TransformGeoJSONRequest(BaseModel):
    geojson: Dict[str, Any]
    source_crs: Optional[str] = None

# CRS detection & transformation
def detect_crs_from_geojson(geojson_data: Dict[str, Any]) -> Optional[str]:
    """
    Try to detect CRS from GeoJSON.
    Returns EPSG code as string or None if not found.
    """
    # Check for CRS in the GeoJSON crs property
    if "crs" in geojson_data:
        crs_info = geojson_data["crs"]
        if isinstance(crs_info, dict):
            if "properties" in crs_info and "name" in crs_info["properties"]:
                crs_name = crs_info["properties"]["name"]
                if isinstance(crs_name, str):
                    # Handle different CRS name formats
                    if "EPSG:" in crs_name:
                        return crs_name
                    elif crs_name.startswith("urn:ogc:def:crs:EPSG::"):
                        epsg_code = crs_name.split("::")[-1]
                        return f"EPSG:{epsg_code}"
    
    return None

def transform_geojson_coordinates(geojson_data: Dict[str, Any], source_crs: str, target_crs: str = "EPSG:4326") -> Dict[str, Any]:
    """
    Transform GeoJSON coordinates from source CRS to target CRS.
    """
    if source_crs == target_crs:
        return geojson_data
    
    try:
        # Create transformer
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        
        def transform_coordinates(coords):
            """Recursively transform coordinates based on geometry type"""
            if not coords:
                return coords
                
            # Check if this is a coordinate pair [x, y] or [x, y, z]
            if isinstance(coords[0], (int, float)):
                if len(coords) >= 2:
                    x, y = transformer.transform(coords[0], coords[1])
                    return [x, y] + coords[2:]  # Keep any additional dimensions
                return coords
            else:
                # Recursively transform nested coordinate arrays
                return [transform_coordinates(coord) for coord in coords]
        
        def transform_geometry(geometry):
            """Transform a single geometry"""
            if not geometry or "coordinates" not in geometry:
                return geometry
            
            transformed_geometry = geometry.copy()
            transformed_geometry["coordinates"] = transform_coordinates(geometry["coordinates"])
            return transformed_geometry
        
        # Create a copy of the input data
        result = json.loads(json.dumps(geojson_data))
        
        # Transform based on GeoJSON type
        if result["type"] == "FeatureCollection":
            for feature in result.get("features", []):
                if "geometry" in feature and feature["geometry"]:
                    feature["geometry"] = transform_geometry(feature["geometry"])
        elif result["type"] == "Feature":
            if "geometry" in result and result["geometry"]:
                result["geometry"] = transform_geometry(result["geometry"])
        else:
            # Direct geometry object
            result = transform_geometry(result)
        
        # Update or add CRS information
        result["crs"] = {
            "type": "name",
            "properties": {
                "name": target_crs
            }
        }
        
        return result
        
    except Exception as e:
        raise ValueError(f"Failed to transform coordinates from {source_crs} to {target_crs}: {str(e)}")

# API endpoints
@app.get("/")
async def root():
    return {"message": "GeoJSON Protected Areas Finder API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/nearest-protected-areas")
async def find_nearest_protected_areas(request: GeoJSONRequest):
    start_time = time.perf_counter()
    logger.info("/api/nearest-protected-areas request started")
    try:
        geojson_data = request.geojson
        logger.debug("[DEBUG] Received GeoJSON payload: %s", json.dumps(geojson_data))
        
        # Validate GeoJSON structure
        if "type" not in geojson_data:
            raise HTTPException(status_code=400, detail="Invalid GeoJSON: missing 'type' field")
        
        # Handle different GeoJSON types
        if geojson_data["type"] == "FeatureCollection":
            if not geojson_data.get("features"):
                raise HTTPException(status_code=400, detail="FeatureCollection has no features")
            # Use the first feature's geometry
            geometry = geojson_data["features"][0]["geometry"]
        elif geojson_data["type"] == "Feature":
            geometry = geojson_data["geometry"]
        else:
            # Assume it's a geometry object
            geometry = geojson_data
        
        # Convert geometry to GeoJSON string for PostGIS
        geometry_json = json.dumps(geometry)
        
        # Protected area types with their table names and display names
        protected_area_types = [
            ("nationalparke", "National Parks"),
            ("naturparke", "Nature Parks"),
            ("naturschutzgebiete", "Nature Reserves"),
            ("landschaftsschutzgebiete", "Landscape Protection Areas"),
            ("biosphaerenreservate", "Biosphere Reserves"),
            ("vogelschutzgebiete", "Bird Protection Areas"),
            ("fauna_flora_habitat_gebiete", "Fauna-Flora-Habitat Areas"),
            ("nationale_naturmonumente", "National Natural Monuments"),
            ("biosphaerenreservate_zonierung", "Biosphere Reserve Zoning")
        ]

        async def query_single_table(table_name, display_name):
            table_start = time.perf_counter()
            logger.info(f"Querying table {table_name} ({display_name})...")
            try:
                async with AsyncSessionLocal() as session:
                    logger.debug("[DEBUG] Checking existence of table %s", table_name)
                    # Check if table exists first
                    check_query = text("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = :table_name
                        );
                    """)
                    table_exists_res = await session.execute(check_query, {"table_name": table_name})
                    exists = table_exists_res.scalar()
                    logger.debug("[DEBUG] table %s exists? %s", table_name, exists)
                    if not exists:
                        logger.info("Skipping %s – table does not exist", table_name)
                        return []

                    # Transform input geometry to EPSG:3035 (if not already)
                    input_geom_3035_query = text("""
                        SELECT ST_Transform(ST_GeomFromGeoJSON(:geom), 3035) AS geom_3035
                    """)
                    logger.debug("[DEBUG] Transforming input GeoJSON to EPSG:3035")
                    input_geom_3035_result = await session.execute(input_geom_3035_query, {"geom": geometry_json})
                    input_geom_3035_wkt = None
                    row = input_geom_3035_result.fetchone()
                    logger.debug("[DEBUG] Raw ST_Transform row for %s: %s", table_name, row)
                    if row:
                        # Get WKT for safe parameter passing
                        get_wkt_query = text("SELECT ST_AsText(:geom) AS wkt")
                        wkt_result = await session.execute(get_wkt_query, {"geom": row[0]})
                        input_geom_3035_wkt = wkt_result.scalar()
                        logger.debug("[DEBUG] WKT for %s: %s", table_name, input_geom_3035_wkt)
                    if not input_geom_3035_wkt:
                        logger.error(f"Failed to transform input geometry to EPSG:3035 for {table_name}")
                        return []

                    # Use geometry functions in native EPSG:3035 (meters)
                    query = text(f"""
                        SELECT 
                            id,
                            name,
                            ST_AsGeoJSON(ST_Transform(geom, 4326)) as geometry,
                            ST_Distance(geom, ST_GeomFromText(:input_geom_3035_wkt, 3035)) / 1000.0 as distance_km,
                            :area_type as area_type
                        FROM {table_name}
                        WHERE ST_DWithin(geom, ST_GeomFromText(:input_geom_3035_wkt, 3035), 10000)
                        ORDER BY geom <-> ST_GeomFromText(:input_geom_3035_wkt, 3035)
                    """)
                    
                    logger.debug("[DEBUG] Running proximity query on %s", table_name)
                    logger.debug("[DEBUG] SQL: %s", query.text)
                    logger.debug("[DEBUG] Params: input_geom_3035_wkt=%s area_type=%s",
                                 input_geom_3035_wkt, display_name)
                    result = await session.execute(query, {
                        "input_geom_3035_wkt": input_geom_3035_wkt,
                        "area_type": display_name
                    })
                    areas = result.fetchall()
                    logger.debug("[DEBUG] Raw rows from %s: %r", table_name, areas)
                    logger.info(f"Table {table_name}: {len(areas)} results, took {time.perf_counter() - table_start:.3f}s")
                    features = []
                    for area in areas:
                        geometry_dict = json.loads(area.geometry)
                        feature = {
                            "type": "Feature",
                            "properties": {
                                "id": area.id,
                                "name": area.name,
                                "distance_km": round(area.distance_km, 2),
                                "area_type": area.area_type,
                                "table_name": table_name
                            },
                            "geometry": geometry_dict
                        }
                        features.append(feature)
                    return features
            except Exception as e:
                logger.error(f"Error querying {table_name}: {e}")
                return []

        # Run all queries in parallel, each with its own session
        tasks = [
            query_single_table(table_name, display_name)
            for table_name, display_name in protected_area_types
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_features = []
        for result in results:
            if isinstance(result, list):
                all_features.extend(result)
            elif isinstance(result, Exception):
                print(f"Query failed: {result}")
        all_features.sort(key=lambda x: x["properties"]["distance_km"])
        response = {
            "type": "FeatureCollection",
            "features": all_features
        }
        logger.info(f"/api/nearest-protected-areas completed in {time.perf_counter() - start_time:.3f}s, returned {len(all_features)} features")
        return response
    except Exception as e:
        logger.error(f"/api/nearest-protected-areas error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/api/transform-geojson")
async def transform_endpoint(request: TransformGeoJSONRequest):
    geojson = request.geojson
    src = request.source_crs or detect_crs_from_geojson(geojson)
    if not src:
        raise HTTPException(status_code=400, detail="Could not detect CRS")
    out = transform_geojson_coordinates(geojson, src)
    return {
        "transformed_geojson": out,
        "source_crs": src,
        "target_crs": "EPSG:4326"
    }

@app.get("/api/all-nationalparke")
async def get_all_nationalparke():
    raise HTTPException(status_code=501, detail="Not implemented")