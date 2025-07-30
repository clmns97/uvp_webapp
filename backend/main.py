#!/usr/bin/env python3
import os
import json
import time
import asyncio
import logging

from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from pyproj import Transformer
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Settings
class Settings(BaseSettings):
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://clmns97.github.io"
    ]
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")
    postgres_user: str = os.getenv("POSTGRES_USER", "user")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "password")
    postgres_db: str = os.getenv("POSTGRES_DB", "geoapp")
    database_url: Optional[str] = os.getenv("DATABASE_URL")

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

settings = Settings()

# Logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("uvp_backend")

# FastAPI setup
app = FastAPI(title="GeoJSON Protected Areas Finder", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database engine & session
engine = create_async_engine(settings.db_url)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Pydantic models
class GeoJSONRequest(BaseModel):
    geojson: Dict[str, Any]

class TransformGeoJSONRequest(BaseModel):
    geojson: Dict[str, Any]
    source_crs: Optional[str] = None

# Protected area tables
PROTECTED_AREA_TABLES = [
    ("nationalparke", "National Parks"),
    ("naturparke", "Nature Parks"),
    ("naturschutzgebiete", "Nature Reserves"),
    ("landschaftsschutzgebiete", "Landscape Protection Areas"),
    ("biosphaerenreservate", "Biosphere Reserves"),
    ("vogelschutzgebiete", "Bird Protection Areas"),
    ("fauna_flora_habitat_gebiete", "Fauna-Flora-Habitat Areas"),
    ("nationale_naturmonumente", "National Natural Monuments"),
    ("biosphaerenreservate_zonierung", "Biosphere Reserve Zoning"),
]

# Helpers
def extract_geometry(geojson: Dict[str, Any]) -> Dict[str, Any]:
    geo_type = geojson.get("type")
    if geo_type == "FeatureCollection":
        features = geojson.get("features", [])
        if not features:
            raise ValueError("FeatureCollection has no features")
        return features[0]["geometry"]
    if geo_type == "Feature":
        return geojson.get("geometry")
    # assume plain geometry
    return geojson

def detect_crs(geojson: Dict[str, Any]) -> Optional[str]:
    crs = geojson.get("crs", {}).get("properties", {}).get("name")
    if isinstance(crs, str):
        if crs.startswith("urn:ogc:def:crs:EPSG::"):
            epsg = crs.split("::")[-1]
            return f"EPSG:{epsg}"
        if "EPSG:" in crs:
            return crs
    return None

def transform_geojson(geojson: Dict[str, Any], src: str, dst: str = "EPSG:4326") -> Dict[str, Any]:
    if src == dst:
        return geojson
    transformer = Transformer.from_crs(src, dst, always_xy=True)
    def recurse(coords):
        if isinstance(coords[0], (int, float)):
            x, y = transformer.transform(coords[0], coords[1])
            return [x, y] + coords[2:]
        return [recurse(c) for c in coords]
    def transform_geom(geom):
        return {
            **geom,
            "coordinates": recurse(geom["coordinates"])
        }
    result = json.loads(json.dumps(geojson))
    t = result.get("type")
    if t == "FeatureCollection":
        for f in result["features"]:
            f["geometry"] = transform_geom(f["geometry"])
    elif t == "Feature":
        result["geometry"] = transform_geom(result["geometry"])
    else:
        result = transform_geom(result)
    result["crs"] = {"type": "name", "properties": {"name": dst}}
    return result

async def get_input_wkt(session: AsyncSession, geom_json: str) -> str:
    sql = text("""
        SELECT ST_AsText(
            ST_Transform(ST_GeomFromGeoJSON(:g), 3035)
        )
    """)
    res = await session.execute(sql, {"g": geom_json})
    wkt = res.scalar()
    if not wkt:
        raise ValueError("Could not transform input geometry")
    return wkt

async def query_table(
    session: AsyncSession,
    table: str,
    label: str,
    input_wkt: str
) -> List[Dict[str, Any]]:
    # ensure table exists
    exists_sql = text("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :t
        )
    """)
    exists = (await session.execute(exists_sql, {"t": table})).scalar()
    if not exists:
        logger.info(f"Skipping {table}: does not exist")
        return []

    qry = text(f"""
        SELECT id, name,
               ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geo,
               ST_Distance(
                   geom,
                   ST_GeomFromText(:wkt, 3035)
               )/1000.0 AS dist
        FROM {table}
        WHERE ST_DWithin(
            geom,
            ST_GeomFromText(:wkt, 3035),
            10000
        )
        ORDER BY geom <-> ST_GeomFromText(:wkt, 3035)
    """)
    res = await session.execute(qry, {"wkt": input_wkt})
    features = []
    for id_, name, geo, dist in res.fetchall():
        features.append({
            "type": "Feature",
            "properties": {
                "id": id_,
                "name": name,
                "distance_km": round(dist, 2),
                "area_type": label,
                "table_name": table
            },
            "geometry": json.loads(geo)
        })
    return features

# Endpoints
@app.get("/")
async def root():
    return {"message": "GeoJSON Protected Areas Finder API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/nearest-protected-areas")
async def nearest(request: GeoJSONRequest):
    start = time.perf_counter()
    try:
        geom = extract_geometry(request.geojson)
        geom_json = json.dumps(geom)
    except ValueError as e:
        raise HTTPException(400, str(e))

    async with AsyncSessionLocal() as session:
        try:
            input_wkt = await get_input_wkt(session, geom_json)
        except Exception as e:
            logger.error("Geometry transform failed: %s", e)
            raise HTTPException(500, "Failed to prepare input geometry")

        tasks = [
            query_table(session, tbl, lbl, input_wkt)
            for tbl, lbl in PROTECTED_AREA_TABLES
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    features = []
    for r in results:
        if isinstance(r, list):
            features.extend(r)
        else:
            logger.error("Query error: %s", r)

    features.sort(key=lambda f: f["properties"]["distance_km"])
    logger.info(
        "Completed in %.3fs with %d features",
        time.perf_counter() - start,
        len(features)
    )
    return {"type": "FeatureCollection", "features": features}

@app.post("/api/transform-geojson")
async def transform_ep(request: TransformGeoJSONRequest):
    src = request.source_crs or detect_crs(request.geojson)
    if not src:
        raise HTTPException(400, "Could not detect source CRS")
    transformed = transform_geojson(request.geojson, src)
    return {"transformed_geojson": transformed, "source_crs": src, "target_crs": "EPSG:4326"}

@app.get("/api/all-nationalparke")
async def all_nationalparke():
    raise HTTPException(501, "Not implemented")