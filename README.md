# GeoJSON nationalparke Finder

A full-stack web application for exploring and analyzing German nationalparke (nature parks) using spatial data. The application allows users to interact with a map, click on locations, and find the five nearest nationalparke.

## Features

- Interactive map-based UI for exploring nationalparke in Germany
- Click anywhere on the map to find the 5 nearest nationalparke
- Display all nationalparke as GeoJSON polygons for visualization
- Uses open data from BfN (Bundesamt für Naturschutz) via WFS
- Modern React frontend with MapLibre GL JS
- FastAPI backend with PostGIS spatial queries
- Fully containerized with Docker

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd uvp_webapp
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file with your desired configuration. The default values work for local development.

3. **Start the application**
   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8001
   - Database: localhost:5434

## Environment Configuration

The application uses a `.env` file for configuration. Copy `.env.example` to `.env` and customize as needed:

### Database Settings
- `POSTGRES_HOST`: Database host (default: `db` for Docker)
- `POSTGRES_PORT`: Database port (default: `5432`)
- `POSTGRES_USER`: Database username
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_DB`: Database name
- `DATABASE_URL`: Complete database connection string (auto-constructed if not provided)

### Network Settings
- `FRONTEND_PORT`: Frontend port mapping (default: `5173`)
- `BACKEND_PORT`: Backend port mapping (default: `8001`)
- `DB_PORT`: Database port mapping (default: `5434`)
- `VITE_API_URL`: API endpoint for frontend (default: `http://localhost:8001`)

### WFS Data Source
- `WFS_URL`: WFS server URL for data loading
- `WFS_LAYER`: WFS layer name for data loading

## Architecture

- **Frontend**: React 18 + MapLibre GL JS + Vite
- **Backend**: FastAPI + SQLAlchemy (async) + GeoAlchemy2
- **Database**: PostgreSQL 15 + PostGIS 3.3
- **Containerization**: Docker + Docker Compose

## Development

The application supports hot reloading for development:

- Frontend changes are automatically reflected via Vite
- Backend changes trigger uvicorn reload
- Database schema is initialized automatically

## Data Sources

The application loads real spatial data from:
- BfN (Bundesamt für Naturschutz) WFS services
- German nationalparke, Nationalparke, and other protected areas
- Data is automatically fetched and loaded during database initialization

## API Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `POST /api/nearest-nationalparke` - Find nearest parks to a point
- `GET /api/all-nationalparke` - Get all parks for visualization

## Troubleshooting

### Database Connection Issues
1. Ensure your `.env` file has correct database credentials
2. Check that the database service is running: `docker-compose ps`
3. View database logs: `docker-compose logs db`

### Port Conflicts
If the default ports are already in use, update them in your `.env` file:
```bash
FRONTEND_PORT=3000
BACKEND_PORT=8080
DB_PORT=5433
```