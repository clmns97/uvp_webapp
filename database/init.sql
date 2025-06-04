-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create parks table
CREATE TABLE parks (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    geom GEOMETRY(POLYGON, 4326) NOT NULL
);

-- Create spatial index for better performance
CREATE INDEX idx_parks_geom ON parks USING GIST (geom);

-- Insert sample nature parks data (using real coordinates for variety)
INSERT INTO parks (name, geom) VALUES 
(
    'Central Park',
    ST_GeomFromText('POLYGON((-73.9812 40.7681, -73.9581 40.7681, -73.9581 40.7640, -73.9812 40.7640, -73.9812 40.7681))', 4326)
),
(
    'Golden Gate Park',
    ST_GeomFromText('POLYGON((-122.5100 37.7694, -122.4534 37.7694, -122.4534 37.7663, -122.5100 37.7663, -122.5100 37.7694))', 4326)
),
(
    'Griffith Park',
    ST_GeomFromText('POLYGON((-118.2937 34.1365, -118.2584 34.1365, -118.2584 34.1184, -118.2937 34.1184, -118.2937 34.1365))', 4326)
),
(
    'Balboa Park',
    ST_GeomFromText('POLYGON((-117.1550 32.7341, -117.1434 32.7341, -117.1434 32.7273, -117.1550 32.7273, -117.1550 32.7341))', 4326)
),
(
    'Millennium Park',
    ST_GeomFromText('POLYGON((-87.6250 41.8826, -87.6210 41.8826, -87.6210 41.8819, -87.6250 41.8819, -87.6250 41.8826))', 4326)
),
(
    'Hyde Park',
    ST_GeomFromText('POLYGON((-0.1652 51.5074, -0.1588 51.5074, -0.1588 51.5020, -0.1652 51.5020, -0.1652 51.5074))', 4326)
),
(
    'Prospect Park',
    ST_GeomFromText('POLYGON((-73.9692 40.6782, -73.9617 40.6782, -73.9617 40.6600, -73.9692 40.6600, -73.9692 40.6782))', 4326)
),
(
    'Phoenix Park',
    ST_GeomFromText('POLYGON((-6.3097 53.3595, -6.2958 53.3595, -6.2958 53.3559, -6.3097 53.3559, -6.3097 53.3595))', 4326)
),
(
    'Tiergarten',
    ST_GeomFromText('POLYGON((13.3502 52.5145, 13.3705 52.5145, 13.3705 52.5080, 13.3502 52.5080, 13.3502 52.5145))', 4326)
),
(
    'Villa Borghese',
    ST_GeomFromText('POLYGON((12.4823 41.9142, 12.4954 41.9142, 12.4954 41.9094, 12.4823 41.9094, 12.4823 41.9142))', 4326)
);