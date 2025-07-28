# Project Design: GeoJSON Protected Areas Finder

## Overview
This project is a full-stack web application for exploring and analyzing German protected areas (including national parks, nature parks, reserves, and more) using spatial data. The application allows users to interact with a map, click on locations, or upload GeoJSON files to find the nearest protected areas. The stack includes a React frontend, a FastAPI backend, and a PostgreSQL/PostGIS database, all orchestrated with Docker Compose.

## Goals
- Provide an interactive map-based UI for users to explore protected areas in Germany.
- Allow users to click on any location or upload a GeoJSON file and retrieve the nearest protected areas using spatial queries.
- Display all supported protected area types as GeoJSON polygons for visualization and debugging.
- Use open data from BfN (Bundesamt für Naturschutz) via WFS for initial data population.
- Ensure the system is easily deployable and reproducible using Docker.

## Architecture
- **Frontend:** React app using MapLibre GL JS with react-map-gl wrapper for map rendering. Uses Carto Light basemap tiles. Communicates with the backend via REST API.
- **Backend:** FastAPI app providing endpoints for spatial queries and data retrieval. Uses async SQLAlchemy with asyncpg driver for database access. Supports multiple protected area types.
- **Database:** PostgreSQL 17 with PostGIS 3 extension for spatial data storage and queries. Data is loaded from BfN WFS server using GDAL/ogr2ogr.
- **Docker:** Each component (frontend, backend, database) runs in its own container. Docker Compose manages service orchestration with environment variable configuration.

## Current Implementation Details

### Frontend (React + MapLibre)
- **Port:** 5173 (configurable via FRONTEND_PORT environment variable)
- **Map Library:** MapLibre GL JS v4.1.0 with react-map-gl v7.1.7
- **Basemap:** Carto Light tiles from basemaps.cartocdn.com with 2x resolution support
- **Initial View:** Centered on Germany (longitude: 10.4515, latitude: 51.1657) at zoom level 5
- **API Communication:** Configurable via VITE_API_URL environment variable (defaults to http://localhost:8000)
- **Features:**
  - Click on the map to find nearest protected areas
  - Drag & drop or upload GeoJSON files to search by custom geometry
  - Results panel groups areas by type and shows distances
  - Visualizes both uploaded geometry and protected areas on the map
  - Loading and error states, clear/reset controls
- **Development:** Vite dev server with hot reloading, polling enabled for Docker compatibility

### Backend (FastAPI)
- **Port:** 8000 internal, mapped to configurable host port via BACKEND_PORT
- **Database:** Async connection using postgresql+asyncpg driver with fallback construction from individual environment variables
- **Endpoints:**
  - `GET /` - Root endpoint with API information
  - `GET /health` - Health check endpoint
  - `POST /api/nearest-protected-areas` - Find nearest protected areas to a given geometry (point, feature, or feature collection)
  - `POST /api/transform-geojson` - Transform uploaded GeoJSON to WGS84 (EPSG:4326) if needed
  - `GET /api/all-nationalparke` - (Not implemented)
- **CORS:** Configured for localhost:5173, localhost:3000, and GitHub Pages
- **Startup:** Database initialization via separate script (init_db.py) with comprehensive WFS data loading

### Database (PostgreSQL + PostGIS)
- **Port:** 5432 internal, mapped to configurable host port via DB_PORT
- **Version:** PostgreSQL 17 with PostGIS 3 (latest packages)
- **Data Sources:** Multiple BfN WFS endpoints for all supported protected area types:
  - National Parks, Nature Parks, Nature Reserves, Landscape Protection Areas, Biosphere Reserves, Bird Protection Areas, Fauna-Flora-Habitat Areas, National Natural Monuments, Biosphere Reserve Zoning
- **Coordinate System:** Data transformed to EPSG:3035 (ETRS89-extended / LAEA Europe)
- **Tables:** One table per protected area type, with columns: id, name, geom
- **Initialization:** Comprehensive init_db.py script with smart table checking and conditional loading

## User Flow
1. **Landing Page:** User sees a map centered on Germany with a header showing "GeoJSON Protected Areas Finder" and control buttons.
2. **Find Nearest Protected Areas:** User clicks on the map or uploads a GeoJSON file. The frontend sends the geometry as GeoJSON to the backend, which returns the nearest protected areas as a GeoJSON FeatureCollection with distance information. Results are displayed both on the map (colored polygons) and in a floating results panel grouped by area type.
3. **Clear Results:** User can click "Clear Results" to remove all markers, polygons, and reset the interface.
4. **Interactive Elements:** Clicked locations show a red marker and popup with coordinates. Loading states and error messages provide user feedback.

## Data Flow
- **Data Loading:** On application startup, a Python script waits for PostgreSQL readiness, enables PostGIS extension, then uses ogr2ogr to fetch multiple datasets from BfN WFS servers. The script checks for existing tables and only loads missing data, supporting all protected area types.
- **Spatial Query:** The backend receives a GeoJSON geometry, performs spatial queries using PostGIS, calculates distances in kilometers, and returns the results as GeoJSON FeatureCollection with CRS transformation from EPSG:3035 to EPSG:4326.
- **Frontend Display:** The frontend renders results using MapLibre layers - protected areas colored by type, uploaded geometry in red, plus markers and popups.

## Technical Specifications

### Spatial Query Implementation
- Uses PostGIS for accurate distance calculations
- Queries all protected area tables in parallel
- ST_DWithin and ST_Distance for proximity and distance
- Results grouped and sorted by distance
- Automatic coordinate system transformation (EPSG:3035 → EPSG:4326)

### Error Handling
- Robust GeoJSON validation supporting Point, Feature, and FeatureCollection inputs
- CRS detection and transformation for uploaded files
- Frontend error display with user-friendly messages
- Backend graceful degradation if WFS data loading fails
- Database connection retry logic
- Subprocess timeout handling for WFS operations

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
- **Multiple Datasets:** Supports loading all protected area types from BfN WFS services
- **Robust Error Handling:** Timeout protection, skip failures, and detailed logging
- **PostGIS Setup:** Automatic extension installation and version reporting
- **Performance Optimizations:** Disabled WFS paging, multigeometry promotion, and validation fixes

## Future Plans
- Add user authentication for saving favorite locations or parks.
- Support additional spatial queries (e.g., areas within a radius, filtering by attributes).
- Improve UI/UX with more map controls and information popups.
- Add automated tests and CI/CD pipeline.
- Enable deployment to cloud platforms.
- Implement proper zoom-to-extent functionality for search results.
- Extend to support additional protected area types or custom datasets.

## Technologies Used
- **Frontend:** React 18.2.0, MapLibre GL JS 4.1.0, react-map-gl 7.1.7, Vite 5.0.0
- **Backend:** FastAPI 0.104.1, SQLAlchemy 2.0.23 (async), asyncpg 0.29.0, GeoAlchemy2 0.14.2, Pydantic 2.5.0, python-dotenv 1.0.0, pyproj, shapely
- **Database:** PostgreSQL 17, PostGIS 3, psycopg2-binary 2.9.9
- **Spatial Tools:** GDAL/ogr2ogr for WFS data import with comprehensive configuration
- **Infrastructure:** Docker, Docker Compose with environment variable configuration
- **Basemap:** Carto Light tiles with multiple CDN endpoints and attribution

---
This document describes the current implementation and future direction for the GeoJSON Protected Areas Finder project.
