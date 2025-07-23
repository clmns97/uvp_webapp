from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_Distance, ST_GeomFromGeoJSON, ST_AsGeoJSON
from shapely.geometry import shape
import json
import os
import subprocess
import asyncio
from typing import Dict, Any, List
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
            # Query to find 5 nearest nationalparke with CRS transformation
            # Input geometry is in EPSG:4326, database geometries are in EPSG:3035
            query = text("""
                SELECT 
                    id,
                    name,
                    ST_AsGeoJSON(ST_Transform(geom, 4326)) as geometry,
                    ST_Distance(
                        ST_Transform(geom, 4326)::geography, 
                        ST_GeomFromGeoJSON(:geom)::geography
                    ) as distance_meters
                FROM nationalparke 
                ORDER BY ST_Transform(geom, 4326)::geography <-> ST_GeomFromGeoJSON(:geom)::geography
                LIMIT 5
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
                        "distance_meters": round(park.distance_meters, 2)
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