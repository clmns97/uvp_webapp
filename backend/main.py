from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_Distance, ST_GeomFromGeoJSON, ST_AsGeoJSON
from shapely.geometry import shape
from pyproj import Transformer, CRS
import json
import os
import subprocess
import asyncio
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Load environment variables from .env file
load_dotenv()

async def initialize_database():
    """Initialize database with WFS data if needed"""
    try:
        print("🔍 Checking database initialization...")
        
        # Set environment variables for the init script
        env = os.environ.copy()
        env.update({
            'POSTGRES_HOST': 'db',  # Docker service name
            'POSTGRES_PORT': '5432',
            'POSTGRES_USER': os.getenv('POSTGRES_USER', 'user'),
            'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD', 'password'),
            'POSTGRES_DB': os.getenv('POSTGRES_DB', 'geoapp')
        })
        
        # Run the initialization script
        result = subprocess.run(
            ['python3', 'init_db.py'],
            capture_output=True,
            text=True,
            env=env,
            timeout=1800  # 30 minute timeout
        )
        
        if result.returncode == 0:
            print("✅ Database initialization completed successfully")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"⚠️  Database initialization had issues:")
            if result.stderr:
                print(result.stderr)
            if result.stdout:
                print(result.stdout)
                
    except subprocess.TimeoutExpired:
        print("⏰ Database initialization timed out")
    except Exception as e:
        print(f"❌ Error during database initialization: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_database()
    yield
    # Shutdown
    pass

app = FastAPI(title="GeoJSON nationalparke Finder", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup - use environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Construct from individual components if DATABASE_URL not provided
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "user")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    database = os.getenv("POSTGRES_DB", "geoapp")
    DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class GeoJSONRequest(BaseModel):
    geojson: Dict[str, Any]

class TransformGeoJSONRequest(BaseModel):
    geojson: Dict[str, Any]
    source_crs: Optional[str] = None  # e.g., "EPSG:3035"

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

@app.get("/")
async def root():
    return {"message": "GeoJSON nationalparke Finder API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/nearest-nationalparke")
async def find_nearest_nationalparke(request: GeoJSONRequest):
    try:
        geojson_data = request.geojson
        
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
        
        async with AsyncSessionLocal() as session:
            # Query to find nationalparke within 50km with CRS transformation
            # Input geometry is in EPSG:4326, database geometries are in EPSG:3035
            query = text("""
                SELECT 
                    id,
                    name,
                    ST_AsGeoJSON(ST_Transform(geom, 4326)) as geometry,
                    ST_Distance(
                        ST_Transform(geom, 4326)::geography, 
                        ST_GeomFromGeoJSON(:geom)::geography
                    ) / 1000.0 as distance_km
                FROM nationalparke 
                WHERE ST_Distance(
                    ST_Transform(geom, 4326)::geography, 
                    ST_GeomFromGeoJSON(:geom)::geography
                ) <= 50000
                ORDER BY ST_Transform(geom, 4326)::geography <-> ST_GeomFromGeoJSON(:geom)::geography
            """)
            
            result = await session.execute(query, {"geom": geometry_json})
            nationalparke = result.fetchall()
            
            # Format response as GeoJSON FeatureCollection
            features = []
            for park in nationalparke:
                geometry_dict = json.loads(park.geometry)
                feature = {
                    "type": "Feature",
                    "properties": {
                        "id": park.id,
                        "name": park.name,
                        "distance_km": round(park.distance_km, 2)
                    },
                    "geometry": geometry_dict
                }
                features.append(feature)
            
            response = {
                "type": "FeatureCollection",
                "features": features
            }
            
            return response
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/api/transform-geojson")
async def transform_geojson(request: TransformGeoJSONRequest):
    """
    Transform GeoJSON from any supported CRS to WGS84 (EPSG:4326).
    Detects CRS automatically or uses provided source_crs.
    """
    try:
        geojson_data = request.geojson
        source_crs = request.source_crs
        
        # Validate GeoJSON structure
        if "type" not in geojson_data:
            raise HTTPException(status_code=400, detail="Invalid GeoJSON: missing 'type' field")
        
        # Try to detect CRS if not provided
        if not source_crs:
            detected_crs = detect_crs_from_geojson(geojson_data)
            if detected_crs:
                source_crs = detected_crs
                print(f"Detected CRS: {source_crs}")
            else:
                # Check coordinate ranges to guess CRS
                # This is a heuristic approach - not always accurate
                coords = []
                
                def extract_coords(obj):
                    if isinstance(obj, dict):
                        if obj.get("type") == "FeatureCollection":
                            for feature in obj.get("features", []):
                                extract_coords(feature)
                        elif obj.get("type") == "Feature":
                            extract_coords(obj.get("geometry", {}))
                        elif "coordinates" in obj:
                            coords.extend(flatten_coordinates(obj["coordinates"]))
                
                def flatten_coordinates(coord_array):
                    """Flatten nested coordinate arrays to get all coordinate pairs"""
                    result = []
                    if isinstance(coord_array, list) and len(coord_array) > 0:
                        if isinstance(coord_array[0], (int, float)):
                            # This is a coordinate pair
                            if len(coord_array) >= 2:
                                result.append((coord_array[0], coord_array[1]))
                        else:
                            # Nested array
                            for item in coord_array:
                                result.extend(flatten_coordinates(item))
                    return result
                
                extract_coords(geojson_data)
                
                if coords:
                    # Check if coordinates are in typical EPSG:3035 range (Europe)
                    x_coords = [c[0] for c in coords[:10]]  # Sample first 10 coordinates
                    y_coords = [c[1] for c in coords[:10]]
                    
                    # EPSG:3035 typically has coordinates in millions for Europe
                    if (min(x_coords) > 1000000 and max(x_coords) < 8000000 and 
                        min(y_coords) > 1000000 and max(y_coords) < 6000000):
                        source_crs = "EPSG:3035"
                        print(f"Guessed CRS based on coordinate range: {source_crs}")
                    elif (min(x_coords) >= -180 and max(x_coords) <= 180 and 
                          min(y_coords) >= -90 and max(y_coords) <= 90):
                        # Already in WGS84
                        return {
                            "transformed_geojson": geojson_data,
                            "source_crs": "EPSG:4326",
                            "target_crs": "EPSG:4326",
                            "message": "GeoJSON is already in WGS84 (EPSG:4326)"
                        }
        
        if not source_crs:
            raise HTTPException(
                status_code=400, 
                detail="Could not detect CRS. Please specify source_crs parameter (e.g., 'EPSG:3035')"
            )
        
        # Transform to WGS84
        transformed_geojson = transform_geojson_coordinates(geojson_data, source_crs, "EPSG:4326")
        
        return {
            "transformed_geojson": transformed_geojson,
            "source_crs": source_crs,
            "target_crs": "EPSG:4326",
            "message": f"Successfully transformed from {source_crs} to EPSG:4326"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error transforming GeoJSON: {str(e)}")

@app.get("/api/all-nationalparke")
async def get_all_nationalparke():
    """Get all nationalparke for debugging/testing purposes"""
    try:
        async with AsyncSessionLocal() as session:
            # Transform geometries from EPSG:3035 to EPSG:4326 for web display
            query = text("""
                SELECT 
                    id,
                    name,
                    ST_AsGeoJSON(ST_Transform(geom, 4326)) as geometry
                FROM nationalparke
            """)
            
            result = await session.execute(query)
            nationalparke = result.fetchall()
            
            features = []
            for park in nationalparke:
                geometry_dict = json.loads(park.geometry)
                feature = {
                    "type": "Feature",
                    "properties": {
                        "id": park.id,
                        "name": park.name
                    },
                    "geometry": geometry_dict
                }
                features.append(feature)
            
            return {
                "type": "FeatureCollection",
                "features": features
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching nationalparke: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)