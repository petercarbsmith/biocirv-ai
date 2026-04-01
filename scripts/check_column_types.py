import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import subprocess

def get_secret(secret_name):
    try:
        cmd = f"pixi run -e deployment gcloud secrets versions access latest --secret={secret_name}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None

def check_types():
    DB_USER = "biocirv_readonly"
    DB_NAME = "biocirv-staging"
    DB_HOST = "127.0.0.1"
    DB_PORT = "5434"
    DB_PASS = get_secret("biocirv-staging-ro-biocirv_readonly")
    
    if not DB_PASS:
        print("Could not get password")
        return

    url = f'postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    engine = create_engine(url)
    
    query = """
    SELECT table_schema, table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_name IN ('analysis_data_view', 'usda_census_view')
    AND column_name = 'value';
    """
    
    try:
        with engine.connect() as conn:
            print("--- Column Type Info ---")
            result = conn.execute(text(query))
            for row in result:
                print(f"Table: {row.table_schema}.{row.table_name} | Column: {row.column_name} | Type: {row.data_type}")
            
            # Also sample data
            print("\n--- Sample values from analysis_data_view ---")
            res = conn.execute(text("SELECT value FROM ca_biositing.analysis_data_view WHERE value IS NOT NULL LIMIT 5"))
            for row in res:
                print(f"Value: {row[0]!r} type: {type(row[0])}")

            print("\n--- Sample values from usda_census_view ---")
            res = conn.execute(text("SELECT value FROM ca_biositing.usda_census_view WHERE value IS NOT NULL LIMIT 5"))
            for row in res:
                print(f"Value: {row[0]!r} type: {type(row[0])}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_types()
