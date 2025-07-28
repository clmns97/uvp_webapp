#!/usr/bin/env python3
"""
Comprehensive database initialization script for GeoJSON nationalparke Finder
Handles PostGIS setup, table creation, and WFS data loading in one place
"""
from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("init_db")

import os
import sys
import time
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def wait_for_postgres(max_retries=30):
    dsn = os.getenv('IMPORT_DATABASE_URL')
    conn_args = {'dsn': dsn} if dsn else {
        'host': os.getenv('IMPORT_PGHOST'),
        'port': os.getenv('IMPORT_PGPORT'),
        'user': os.getenv('IMPORT_PGUSER'),
        'password': os.getenv('IMPORT_PGPASSWORD'),
        'database': os.getenv('IMPORT_PGDATABASE'),
        'sslmode': os.getenv('IMPORT_PGSSLMODE', 'require'),
    }
    for attempt in range(1, max_retries+1):
        try:
            conn = psycopg2.connect(**conn_args)
            conn.close()
            print(f"✓ PostgreSQL ready after {attempt} tries")
            return conn_args
        except psycopg2.OperationalError as e:
            print(f"⏳ Waiting for PostgreSQL (attempt {attempt}/{max_retries}): {e}")
            time.sleep(2)
    print(f"✗ Could not connect after {max_retries} attempts")
    sys.exit(1)

def setup_postgis(db_config):
    """Initialize database with PostGIS extensions and create tables"""
    try:
        conn = psycopg2.connect(**db_config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info("🗺️  Setting up PostGIS extensions...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology;")
        
        # Check PostGIS version
        cursor.execute("SELECT PostGIS_Version();")
        version = cursor.fetchone()[0]
        logger.info(f"✅ PostGIS version: {version}")
            
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.info(f"❌ Error setting up PostGIS: {e}")
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
        logger.info(f"❌ Error checking table {table_name}: {e}")
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
        logger.info(f"⚠️  Could not count records in {table_name}: {e}")
        return 0

def execute_custom_transformations(db_config):
    """Execute custom SQL transformations to fix column naming issues"""
    try:
        conn = psycopg2.connect(**db_config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info("\n🔧 Applying custom table transformations...")
        
        # Only transform fauna_flora_habitat_gebiete table
        if check_table_exists(db_config, "fauna_flora_habitat_gebiete"):
            logger.info("🔨 Adding name column to fauna_flora_habitat_gebiete from gebietsname...")
            
            try:
                # Check if gebietsname column exists and name doesn't
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'fauna_flora_habitat_gebiete' 
                            AND column_name = 'gebietsname'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'fauna_flora_habitat_gebiete' 
                            AND column_name = 'name'
                        ) THEN
                            -- Add name column and copy data from gebietsname
                            ALTER TABLE fauna_flora_habitat_gebiete ADD COLUMN name VARCHAR;
                            UPDATE fauna_flora_habitat_gebiete SET name = gebietsname;
                            RAISE NOTICE 'Added name column to fauna_flora_habitat_gebiete from gebietsname';
                        ELSE
                            RAISE NOTICE 'Transformation not needed for fauna_flora_habitat_gebiete';
                        END IF;
                    END
                    $$;
                """)
                
                logger.info("✅ Successfully applied transformation to fauna_flora_habitat_gebiete")
                
            except Exception as e:
                logger.info(f"⚠️  Error applying transformation to fauna_flora_habitat_gebiete: {e}")
        else:
            logger.info("⏭️  Skipping fauna_flora_habitat_gebiete - table does not exist")
        
        cursor.close()
        conn.close()
        
        logger.info("🎯 Transformation completed")
        return True
        
    except Exception as e:
        logger.info(f"❌ Error during custom transformations: {e}")
        return False

def load_wfs_data(db_config):
    """Load real data from German BfN WFS services - only for missing tables"""
    
    # Database connection string for ogr2ogr - use the Docker service host
    db_url = os.getenv('IMPORT_DATABASE_URL')
    db_connection = f"PG:{db_url}"
    
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
    
    logger.info("\n🔍 Checking existing tables...")
    
    for source in wfs_sources:
        table_name = source['table']
        
        # Check if table exists and has data
        if check_table_exists(db_config, table_name):
            record_count = get_table_count(db_config, table_name)
            if record_count > 0:
                logger.info(f"✅ {table_name} already exists with {record_count} records - skipping")
                skipped_count += 1
                continue
            else:
                logger.info(f"⚠️  {table_name} exists but is empty - reloading...")
        else:
            logger.info(f"❌ {table_name} does not exist - loading...")
        
        try:
            logger.info(f"\n🌍 Loading {source['description']}...")
            
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
                '-lco', 'FID=id',
                '-nlt', 'PROMOTE_TO_MULTI',
                '-nlt', 'CONVERT_TO_LINEAR', 
                '-nlt', 'MultiPolygon',
                '-skipfailures',
                '-forceNullable',
                '-makevalid',
                '--config', 'OGR_WFS_PAGING_ALLOWED', 'ON',
                '--config', 'OGR_WFS_PAGE_SIZE', '1000',
                '--config', 'CPL_DEBUG', 'OFF'  # Reduce verbose output
            ]
            
            logger.info(f"📡 Fetching layer '{source['layer']}' from WFS...")
            logger.info(f"🔗 URL: {wfs_url}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)  # 15 min timeout
            
            if result.returncode == 0:
                count = get_table_count(db_config, source['table'])
                logger.info(f"✅ {source['table']} loaded successfully with {count} records!")
                success_count += 1
                    
            else:
                logger.info(f"❌ Error loading {source['table']}:")
                logger.info(f"   STDERR: {result.stderr}")
                logger.info(f"   STDOUT: {result.stdout}")
                
        except subprocess.TimeoutExpired:
            logger.info(f"⏰ Timeout loading {source['table']}")
        except Exception as e:
            logger.info(f"❌ Error loading {source['table']}: {e}")
    
    total_processed = success_count + skipped_count
    logger.info(f"\n🎯 WFS Loading Summary:")
    logger.info(f"   📊 {success_count} tables loaded from WFS")
    logger.info(f"   ⏭️  {skipped_count} tables skipped (already exist)")
    logger.info(f"   ✅ {total_processed}/{len(wfs_sources)} tables ready")
    
    return total_processed > 0

def main():
    """Main initialization function"""
    logger.info("🚀 Starting database initialization...")
    
    # Wait for PostgreSQL
    db_config = wait_for_postgres()
    
    # Setup PostGIS and tables
    if not setup_postgis(db_config):
        logger.info("❌ PostGIS setup failed!")
        sys.exit(1)
    
    # Load WFS data (only missing tables)
    if load_wfs_data(db_config):
        logger.info("🎉 WFS data loading completed!")
    else:
        logger.info("⚠️  No tables were loaded - check WFS connectivity")
    
    # Apply custom transformations to fix column naming issues
    if execute_custom_transformations(db_config):
        logger.info("🎉 Custom transformations completed!")
    else:
        logger.info("⚠️  Custom transformations had issues")
    
    logger.info("✅ Ready for application use!")

if __name__ == "__main__":
    main()