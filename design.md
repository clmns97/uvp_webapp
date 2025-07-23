# Project Design: GeoJSON nationalparke Finder

## Overview
This project is a full-stack web application for exploring and analyzing German nationalparke (nature parks) using spatial data. The application allows users to interact with a map, click on locations, and find the five nearest nationalparke. It also provides the ability to visualize all nationalparke on the map. The stack includes a React frontend, a FastAPI backend, and a PostgreSQL/PostGIS database, all orchestrated with Docker Compose.

## Goals
- Provide an interactive map-based UI for users to explore nationalparke in Germany.
- Allow users to click on any location and retrieve the five nearest nationalparke using spatial queries.
- Display all nationalparke as GeoJSON polygons for visualization and debugging.
- Use open data from BfN (Bundesamt für Naturschutz) via WFS for initial data population.
- Ensure the system is easily deployable and reproducible using Docker.

## Architecture
- **Frontend:** React app using MapLibre GL JS with react-map-gl wrapper for map rendering. Uses Carto Light basemap tiles. Communicates with the backend via REST API.
- **Backend:** FastAPI app providing endpoints for spatial queries and data retrieval. Uses async SQLAlchemy with asyncpg driver for database access.
- **Database:** PostgreSQL 17 with PostGIS 3 extension for spatial data storage and queries. Data is loaded from BfN WFS server using GDAL/ogr2ogr.
- **Docker:** Each component (frontend, backend, database) runs in its own container. Docker Compose manages service orchestration with environment variable configuration.

## Current Implementation Details

### Frontend (React + MapLibre)
- **Port:** 5173 (configurable via FRONTEND_PORT environment variable)
- **Map Library:** MapLibre GL JS v4.1.0 with react-map-gl v7.1.7
- **Basemap:** Carto Light tiles from basemaps.cartocdn.com with 2x resolution support
- **Initial View:** Centered on coordinates (longitude: 51.416667, latitude: 9.483333) at zoom level 10
- **API Communication:** Configurable via VITE_API_URL environment variable (defaults to http://localhost:8000)
- **Development:** Vite dev server with hot reloading, polling enabled for Docker compatibility

### Backend (FastAPI)
- **Port:** 8000 internal, mapped to configurable host port via BACKEND_PORT
- **Database:** Async connection using postgresql+asyncpg driver with fallback construction from individual environment variables
- **Endpoints:**
  - `GET /` - Root endpoint with API information
  - `GET /health` - Health check endpoint
  - `POST /api/nearest-nationalparke` - Find 5 nearest parks to a given point
  - `GET /api/all-nationalparke` - Retrieve all parks for debugging/visualization
- **CORS:** Configured for localhost:5173 and localhost:3000
- **Startup:** Automatic database initialization via lifespan events with comprehensive WFS data loading

### Database (PostgreSQL + PostGIS)
- **Port:** 5432 internal, mapped to configurable host port via DB_PORT
- **Version:** PostgreSQL 17 with PostGIS 3 (latest packages)
- **Data Sources:** Multiple BfN WFS endpoints:
  - `https://geodienste.bfn.de/ogc/wfs/schutzgebiet` with layers:
    - `bfn_sch_Schutzgebiet:Nationalparke` → nationalparke table
    - `bfn_sch_Schutzgebiet:Vogelschutzgebiete` → vogelschutzgebiete table
- **Coordinate System:** Data transformed to EPSG:3035 (ETRS89-extended / LAEA Europe)
- **Tables:** nationalparke and vogelschutzgebiete with columns: id, name, geom
- **Initialization:** Comprehensive init_db.py script with smart table checking and conditional loading

## User Flow
1. **Landing Page:** User sees a map centered on Germany with a header showing "GeoJSON nationalparke Finder" and control buttons.
2. **Find Nearest nationalparke:** User clicks on the map. The frontend sends the clicked coordinates as a GeoJSON Point to the backend, which returns the five nearest nationalparke as a GeoJSON FeatureCollection with distance information. Results are displayed both on the map (green polygons) and in a floating results panel.
3. **Show All nationalparke:** User can click "Show All nationalparke" button to display all nationalparke polygons on the map (blue polygons) for exploration.
4. **Clear Results:** User can click "Clear Results" to remove all markers, polygons, and reset the interface.
5. **Interactive Elements:** Clicked locations show a red marker and popup with coordinates. Loading states and error messages provide user feedback.

## Data Flow
- **Data Loading:** On application startup, a comprehensive Python script waits for PostgreSQL readiness, enables PostGIS extension, then uses ogr2ogr to fetch multiple datasets from BfN WFS servers. The script intelligently checks for existing tables and only loads missing data, supporting both nationalparke and vogelschutzgebiete datasets.
- **Spatial Query:** The backend receives a GeoJSON point, performs a spatial nearest-neighbor query using PostGIS geography functions and KNN operator (<->), calculates distances in meters, and returns the results as GeoJSON FeatureCollection with proper CRS transformation from EPSG:3035 to EPSG:4326.
- **Frontend Display:** The frontend renders results using MapLibre layers - nearest parks in green (#2ecc71) with 70% opacity, all parks in blue (#3498db) with 50% opacity, plus markers and popups.

## Technical Specifications

### Spatial Query Implementation
- Uses PostGIS geography type for accurate distance calculations
- KNN operator (<->) for efficient nearest neighbor search
- ST_Distance function for precise distance measurements in meters
- Results limited to 5 nearest features
- Automatic coordinate system transformation (EPSG:3035 → EPSG:4326)

### Error Handling
- Robust GeoJSON validation supporting Point, Feature, and FeatureCollection inputs
- Frontend error display with user-friendly messages
- Backend graceful degradation if WFS data loading fails
- Database connection retry logic with 60-attempt maximum
- Comprehensive subprocess timeout handling (15-30 minutes) for WFS operations

### Development Features
- Hot reloading enabled for both frontend (Vite with polling) and backend (uvicorn --reload)
- Volume mounts for live code changes during development
- Persistent database storage using Docker volumes
- Smart database initialization that skips existing tables with data

## Port Configuration (Environment Variable Driven)
- **Frontend:** Host ${FRONTEND_PORT} → Container 5173
- **Backend:** Host ${BACKEND_PORT} → Container 8000  
- **Database:** Host ${DB_PORT} → Container 5432

## Environment Variables
- **Frontend:** 
  - `VITE_API_URL` (API endpoint configuration)
- **Backend:** 
  - `DATABASE_URL` (complete PostgreSQL connection string, auto-constructed if not provided)
  - `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- **Docker Compose:**
  - `FRONTEND_PORT`, `BACKEND_PORT`, `DB_PORT` (port mappings)
- **WFS:** Hardcoded URLs and layers in init_db.py for reliability

## Database Initialization Details
- **Smart Loading:** The init_db.py script checks for existing tables and record counts before attempting WFS downloads
- **Multiple Datasets:** Supports loading both Nationalparke and Vogelschutzgebiete from BfN WFS services
- **Robust Error Handling:** Timeout protection, skip failures, and detailed logging
- **PostGIS Setup:** Automatic extension installation and version reporting
- **Performance Optimizations:** Disabled WFS paging, multigeometry promotion, and validation fixes

## Future Plans
- Add user authentication for saving favorite locations or parks.
- Support additional spatial queries (e.g., parks within a radius, filtering by attributes).
- Improve UI/UX with more map controls and information popups.
- Add automated tests and CI/CD pipeline.
- Enable deployment to cloud platforms.
- Implement proper zoom-to-extent functionality for search results.
- Extend to support additional protected area types beyond nationalparke.

## Technologies Used
- **Frontend:** React 18.2.0, MapLibre GL JS 4.1.0, react-map-gl 7.1.7, Vite 5.0.0
- **Backend:** FastAPI 0.104.1, SQLAlchemy 2.0.23 (async), asyncpg 0.29.0, GeoAlchemy2 0.14.2, Pydantic 2.5.0, python-dotenv 1.0.0
- **Database:** PostgreSQL 17, PostGIS 3, psycopg2-binary 2.9.9
- **Spatial Tools:** GDAL/ogr2ogr for WFS data import with comprehensive configuration
- **Infrastructure:** Docker, Docker Compose with environment variable configuration
- **Basemap:** Carto Light tiles with multiple CDN endpoints and attribution

## Why This Approach?
- **Open Data:** Leverages open government data from BfN for transparency and reproducibility.
- **Spatial Database:** PostGIS provides robust spatial query capabilities with geography support for accurate distance calculations.
- **Modern Web Stack:** React and FastAPI offer fast development and scalability with async support.
- **Containerization:** Docker ensures consistent environments and easy deployment across different systems.
- **Flexible Mapping:** MapLibre GL JS provides vector tile support and modern WebGL rendering without vendor lock-in.
- **Environment Flexibility:** Full environment variable support for easy deployment configuration.

---
This document describes the current implementation and future direction for the GeoJSON nationalparke Finder project.
