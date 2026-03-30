import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def test_db():
    load_dotenv()
    DB_USER = os.getenv('DB_USER', 'biocirv_user')
    DB_PASS = os.getenv('DB_PASSWORD', 'biocirv_dev_password')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'biocirv_db')

    url = f'postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    print(f"Connecting to {url.replace(DB_PASS, '****')}")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            # Check views
            q = """
            SELECT schemaname, matviewname as name, 'materialized_view' as type FROM pg_matviews
            WHERE matviewname IN ('analysis_data_view', 'usda_census_view')
            UNION
            SELECT schemaname, viewname as name, 'view' as type FROM pg_views
            WHERE viewname IN ('analysis_data_view', 'usda_census_view')
            """
            result = conn.execute(text(q))
            views = result.fetchall()
            print('Found views:', views)

            # Check analytics schema views
            q_all = "SELECT schemaname, matviewname FROM pg_matviews WHERE schemaname IN ('analytics', 'ca_biositing')"
            result_all = conn.execute(text(q_all))
            print('All mat views in target schemas:', result_all.fetchall())

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_db()
