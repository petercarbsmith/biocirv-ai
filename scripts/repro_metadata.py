import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Mock needed components for local run without full PandasAI if needed, 
# but let's try to use the actual ones since they are in the environment.

def test_metadata_introspection():
    load_dotenv()
    
    # 1. Setup Connection (Mirrors sandbox_setup.py)
    DB_USER = os.getenv('DB_USER', 'biocirv_user')
    DB_PASS = os.getenv('DB_PASSWORD', 'biocirv_dev_password')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5434')
    DB_NAME = os.getenv('DB_NAME', 'biocirv_db')

    # Try both dialects
    dialects = ["postgresql+psycopg2", "postgresql+pg8000"]
    
    views = [
        "ca_biositing.analysis_data_view",
        "data_portal.usda_census_view"
    ]

    for dialect in dialects:
        print(f"\n--- Testing Dialect: {dialect} ---")
        try:
            url = f"{dialect}://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            
            # Simulate the search_path options
            all_schemas = "ca_biositing,data_portal"
            connect_args = {"options": f"-c search_path={all_schemas}"}
            
            engine = create_engine(url, connect_args=connect_args)
            
            with engine.connect() as conn:
                print(f"✅ Connected successfully with {dialect}")
                
                # Check current search path
                res = conn.execute(text("SHOW search_path")).fetchone()
                print(f"Current search_path: {res[0]}")

                for view_path in views:
                    schema, table = view_path.split(".")
                    print(f"\nIntrospecting {view_path}...")
                    
                    # 1. Try SQLAlchemy Inspector
                    from sqlalchemy import inspect
                    inspector = inspect(engine)
                    
                    columns = inspector.get_columns(table, schema=schema)
                    if columns:
                        print(f"  ✅ SQLAlchemy Inspector found {len(columns)} columns for {schema}.{table}")
                    else:
                        print(f"  ❌ SQLAlchemy Inspector found NO columns for {schema}.{table}")

                    # 2. Try WITHOUT explicit schema (relying on search_path)
                    columns_no_schema = inspector.get_columns(table)
                    if columns_no_schema:
                        print(f"  ✅ SQLAlchemy Inspector (no schema) found {len(columns_no_schema)} columns for {table}")
                    else:
                        print(f"  ❌ SQLAlchemy Inspector (no schema) found NO columns for {table}")

        except Exception as e:
            print(f"  ❌ Error with {dialect}: {e}")

if __name__ == "__main__":
    test_metadata_introspection()
