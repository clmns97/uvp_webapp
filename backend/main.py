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
from typing import Dict, Any, List

app = FastAPI(title="GeoJSON Parks Finder", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/geoapp")
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class GeoJSONRequest(BaseModel):
    geojson: Dict[str, Any]

@app.get("/")
async def root():
    return {"message": "GeoJSON Parks Finder API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/nearest-parks")
async def find_nearest_parks(request: GeoJSONRequest):
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
            # Query to find 5 nearest parks using ST_Distance
            query = text("""
                SELECT 
                    id,
                    name,
                    ST_AsGeoJSON(geom) as geometry,
                    ST_Distance(
                        geom::geography, 
                        ST_GeomFromGeoJSON(:geom)::geography
                    ) as distance_meters
                FROM parks 
                ORDER BY geom::geography <-> ST_GeomFromGeoJSON(:geom)::geography
                LIMIT 1
            """)
            
            result = await session.execute(query, {"geom": geometry_json})
            parks = result.fetchall()
            
            # Format response as GeoJSON FeatureCollection
            features = []
            for park in parks:
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

@app.get("/api/all-parks")
async def get_all_parks():
    """Get all parks for debugging/testing purposes"""
    try:
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT 
                    id,
                    name,
                    ST_AsGeoJSON(geom) as geometry
                FROM parks
            """)
            
            result = await session.execute(query)
            parks = result.fetchall()
            
            features = []
            for park in parks:
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
        raise HTTPException(status_code=500, detail=f"Error fetching parks: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)