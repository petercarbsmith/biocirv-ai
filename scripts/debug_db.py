import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import subprocess

def get_secret(secret_name):
    try:
        # Use pixi run -e deployment to run gcloud
        cmd = f"pixi run -e deployment gcloud secrets versions access latest --secret={secret_name}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Error fetching secret {secret_name}: {result.stderr}")
            return None
    except Exception as e:
        print(f"Exception fetching secret {secret_name}: {e}")
        return None

def test_db():
    # Load env from analysis/biocirv-ai/.env if it exists
    env_path = os.path.join('analysis', 'biocirv-ai', '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()

    # Use Cloud SQL Staging settings as per notebook
    DB_USER = "biocirv_readonly"
    DB_NAME = "biocirv-staging"
    DB_HOST = "127.0.0.1"
    DB_PORT = "5434"
    
    # Try to get password from secret manager
    DB_PASS = get_secret("biocirv-staging-ro-biocirv_readonly")
    
    if not DB_PASS:
        print("Falling back to .env or default password")
        DB_PASS = os.getenv('DB_PASSWORD', 'biocirv_dev_password')

    url = f'postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    print(f"Connecting to {url.replace(DB_PASS, '****') if DB_PASS else url}")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            # 1. Check current user and DB
            res = conn.execute(text("SELECT current_user, current_database();"))
            user, db = res.fetchone()
            print(f"Connected as: {user} to database: {db}")

            # 2. Check search_path
            res = conn.execute(text("SHOW search_path;"))
            print(f"Current search_path: {res.fetchone()[0]}")

            # 3. Set search_path and check again
            conn.execute(text("SET search_path TO ca_biositing, data_portal, public;"))
            res = conn.execute(text("SHOW search_path;"))
            print(f"Updated search_path: {res.fetchone()[0]}")

            # 4. Check materialized views population
            print("\n--- Materialized Views Status ---")
            q_mv = """
            SELECT schemaname, matviewname, ispopulated 
            FROM pg_matviews 
            WHERE schemaname IN ('ca_biositing', 'data_portal');
            """
            result_mv = conn.execute(text(q_mv))
            for row in result_mv:
                print(f"Schema: {row.schemaname}, View: {row.matviewname}, Populated: {row.ispopulated}")

            # 5. Try to query data from analysis_data_view
            print("\n--- Querying analysis_data_view (LIMIT 5) ---")
            try:
                # Use explicit schema
                df = pd.read_sql("SELECT * FROM ca_biositing.analysis_data_view LIMIT 5", engine)
                print(f"Found {len(df)} rows in ca_biositing.analysis_data_view")
                if not df.empty:
                    print(df.head())
                else:
                    print("ca_biositing.analysis_data_view is EMPTY")
            except Exception as e:
                print(f"Error querying ca_biositing.analysis_data_view: {e}")

            # 6. Check counts in key views
            print("\n--- Row Counts ---")
            views_to_check = [
                "ca_biositing.analysis_data_view",
                "ca_biositing.usda_census_view",
                "ca_biositing.landiq_record_view"
            ]
            for view in views_to_check:
                try:
                    res = conn.execute(text(f"SELECT count(*) FROM {view}"))
                    count = res.fetchone()[0]
                    print(f"{view}: {count} rows")
                except Exception as e:
                    print(f"Error counting {view}: {e}")

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_db()
