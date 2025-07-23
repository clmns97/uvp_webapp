FROM postgres:17

# Install PostGIS and related packages
RUN apt-get update && apt-get install -y \
    postgresql-17-postgis-3 \
    postgresql-17-postgis-3-scripts \
    postgis \
    && rm -rf /var/lib/apt/lists/*