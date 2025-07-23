#!/usr/bin/env python3
"""
Comprehensive database initialization script for GeoJSON nationalparke Finder
Handles PostGIS setup, table creation, and WFS data loading in one place
"""
import os
import sys
import time
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def wait_for_postgres(max_retries=60):
    """Wait for PostgreSQL to be ready"""
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'db'),  # Use Docker service name
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'user': os.getenv('POSTGRES_USER', 'user'),
        'password': os.getenv('POSTGRES_PASSWORD', 'password'),
        'database': os.getenv('POSTGRES_DB', 'geoapp')
    }
    
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(**db_config)
            conn.close()
            print(f"✓ PostgreSQL is ready after {attempt + 1} attempts")
            return db_config
        except psycopg2.OperationalError:
            print(f"⏳ Waiting for PostgreSQL... (attempt {attempt + 1}/{max_retries})")
            time.sleep(2)
    
    print(f"✗ Failed to connect to PostgreSQL after {max_retries} attempts")
    sys.exit(1)

def setup_postgis(db_config):
    """Initialize database with PostGIS extensions and create tables"""
    try:
        conn = psycopg2.connect(**db_config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("🗺️  Setting up PostGIS extensions...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology;")
        
        # Check PostGIS version
        cursor.execute("SELECT PostGIS_Version();")
        version = cursor.fetchone()[0]
        print(f"✅ PostGIS version: {version}")
            
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error setting up PostGIS: {e}")
        return False

def check_table_exists(db_config, table_name):
    """Check if a table exists in the database"""
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """, (table_name,))
        
        exists = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return exists
        
    except Exception as e:
        print(f"❌ Error checking table {table_name}: {e}")
        return False

def get_table_count(db_config, table_name):
    """Get the number of records in a table"""
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"⚠️  Could not count records in {table_name}: {e}")
        return 0

def load_wfs_data(db_config):
    """Load real data from German BfN WFS services - only for missing tables"""
    
    # Database connection string for ogr2ogr - use the Docker service host
    db_connection = f"PG:host={db_config['host']} " \
                   f"port={db_config['port']} " \
                   f"dbname={db_config['database']} " \
                   f"user={db_config['user']} " \
                   f"password={db_config['password']}"
    
    # WFS sources with updated URLs and layer names
    wfs_sources = [
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Nationale_Naturmonumente',
            'table': 'nationale_naturmonumente',
            'description': 'German National Natural Monuments'
        },
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Fauna_Flora_Habitat_Gebiete',
            'table': 'fauna_flora_habitat_gebiete',
            'description': 'German Fauna-Flora-Habitat Areas'
        },
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Vogelschutzgebiete',
            'table': 'vogelschutzgebiete',
            'description': 'German Bird Protection Areas'
        },
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Biosphaerenreservate',
            'table': 'biosphaerenreservate',
            'description': 'German Biosphere Reserves'
        },
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Biosphaerenreservate_Zonierung',
            'table': 'biosphaerenreservate_zonierung',
            'description': 'German Biosphere Reserve Zoning'
        },
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Nationalparke',
            'table': 'nationalparke',
            'description': 'German National Parks'
        },
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Naturparke',
            'table': 'naturparke',
            'description': 'German Nature Parks'
        },
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Naturschutzgebiete',
            'table': 'naturschutzgebiete',
            'description': 'German Nature Reserves'
        },
        {
            'url': 'https://geodienste.bfn.de/ogc/wfs/schutzgebiet',
            'layer': 'bfn_sch_Schutzgebiet:Landschaftsschutzgebiete',
            'table': 'landschaftsschutzgebiete',
            'description': 'German Landscape Protection Areas'
        }
    ]
    
    success_count = 0
    skipped_count = 0
    
    print("\n🔍 Checking existing tables...")
    
    for source in wfs_sources:
        table_name = source['table']
        
        # Check if table exists and has data
        if check_table_exists(db_config, table_name):
            record_count = get_table_count(db_config, table_name)
            if record_count > 0:
                print(f"✅ {table_name} already exists with {record_count} records - skipping")
                skipped_count += 1
                continue
            else:
                print(f"⚠️  {table_name} exists but is empty - reloading...")
        else:
            print(f"❌ {table_name} does not exist - loading...")
        
        try:
            print(f"\n🌍 Loading {source['description']}...")
            
            # Use ogr2ogr with specific layer targeting to avoid fetching unrelated data
            wfs_url = f"WFS:{source['url']}"
            
            cmd = [
                'ogr2ogr',
                '-f', 'PostgreSQL',
                db_connection,
                wfs_url,
                source['layer'],  # Specify exact layer name as positional argument
                '-nln', source['table'],
                '-overwrite',
                '-progress',
                '-t_srs', 'EPSG:3035',
                '-lco', 'GEOMETRY_NAME=geom',
                '-nlt', 'PROMOTE_TO_MULTI',
                '-nlt', 'CONVERT_TO_LINEAR', 
                '-nlt', 'MultiPolygon',
                '-skipfailures',
                '-forceNullable',
                '-makevalid',
                '--config', 'OGR_WFS_PAGING_ALLOWED', 'OFF',  # Disable automatic paging
                '--config', 'OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN', 'OFF',  # Only load specified layer
                '--config', 'CPL_DEBUG', 'OFF'  # Reduce verbose output
            ]
            
            print(f"📡 Fetching layer '{source['layer']}' from WFS...")
            print(f"🔗 URL: {wfs_url}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)  # 15 min timeout
            
            if result.returncode == 0:
                count = get_table_count(db_config, source['table'])
                print(f"✅ {source['table']} loaded successfully with {count} records!")
                success_count += 1
                    
            else:
                print(f"❌ Error loading {source['table']}:")
                print(f"   STDERR: {result.stderr}")
                print(f"   STDOUT: {result.stdout}")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout loading {source['table']}")
        except Exception as e:
            print(f"❌ Error loading {source['table']}: {e}")
    
    total_processed = success_count + skipped_count
    print(f"\n🎯 WFS Loading Summary:")
    print(f"   📊 {success_count} tables loaded from WFS")
    print(f"   ⏭️  {skipped_count} tables skipped (already exist)")
    print(f"   ✅ {total_processed}/{len(wfs_sources)} tables ready")
    
    return total_processed > 0

def main():
    """Main initialization function"""
    print("🚀 Starting database initialization...")
    
    # Wait for PostgreSQL
    db_config = wait_for_postgres()
    
    # Setup PostGIS and tables
    if not setup_postgis(db_config):
        print("❌ PostGIS setup failed!")
        sys.exit(1)
    
    # Load WFS data (only missing tables)
    if load_wfs_data(db_config):
        print("🎉 Database initialization completed successfully!")
    else:
        print("⚠️  No tables were loaded - check WFS connectivity")
    
    print("✅ Ready for application use!")

if __name__ == "__main__":
    main()