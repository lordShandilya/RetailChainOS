"""
db_setup.py
Purpose: Sets up PostgreSQL databases and tables for RetailChain OS, supporting walmart_db (SmartInventory, RouteAI, TrackX) and postgres (Fulfillment).

Execution: Run before seed_data.py.
Command: python app/smart_inventory/db_setup.py
"""
import psycopg2
from psycopg2 import Error
from dotenv import dotenv_values

ENV_VALUES = dotenv_values(".env")

DB_PARAMS = {
    "dbname": "walmart_db",
    "user": "walmart_user",
    "password": ENV_VALUES["DB_USER_PASSWORD"],
    "host": "localhost",
    "port": "5432"
}

POSTGRES_PARAMS = {
    "dbname": "postgres",
    "user": "postgres",
    "password": ENV_VALUES["POSTGRES_PASSWORD"],
    "host": "localhost",
    "port": "5432"
}

def setup_database():
    """Creates databases and tables."""
    try:
        # Connect to postgres as postgres user
        conn = psycopg2.connect(**POSTGRES_PARAMS)
        conn.autocommit = True
        cur = conn.cursor()

        # Ensure walmart_user exists
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'walmart_user';")
        if cur.fetchone() is None:
            cur.execute(f"CREATE USER walmart_user WITH PASSWORD '{ENV_VALUES['DB_USER_PASSWORD']}';")
        cur.execute("ALTER USER walmart_user WITH CREATEDB;")

        # Create walmart_db
        cur.execute("DROP DATABASE IF EXISTS walmart_db;")
        cur.execute("CREATE DATABASE walmart_db OWNER walmart_user;")

        cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO walmart_user;")
        cur.close()
        conn.close()

        # Connect to walmart_db as postgres to enable PostGIS
        conn = psycopg2.connect(
            dbname="walmart_db",
            user=POSTGRES_PARAMS["user"],
            password=POSTGRES_PARAMS["password"],
            host=POSTGRES_PARAMS["host"],
            port=POSTGRES_PARAMS["port"]
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.close()
        conn.close()

        # Connect to walmart_db as walmart_user
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Create tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS FulfillmentCenter (
                id SERIAL PRIMARY KEY,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                current_workload INTEGER NOT NULL,
                handling_capacity INTEGER NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS InventoryItem (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) NOT NULL,
                quantity INTEGER NOT NULL,
                fulfillment_center_id INTEGER REFERENCES FulfillmentCenter(id) ON DELETE CASCADE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                store_id SERIAL PRIMARY KEY,
                store_location VARCHAR(100) NOT NULL,
                store_address TEXT NOT NULL,
                lat DOUBLE PRECISION NOT NULL,
                lng DOUBLE PRECISION NOT NULL,
                UNIQUE (store_location, store_address)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                inventory_id SERIAL PRIMARY KEY,
                dc_id INTEGER,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                current_stock INTEGER NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                forecast_id SERIAL PRIMARY KEY,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                predicted_demand NUMERIC NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reorder_alerts (
                alert_id SERIAL PRIMARY KEY,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                current_stock INTEGER NOT NULL,
                reorder_threshold INTEGER NOT NULL,
                priority_score FLOAT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS delivery_routes (
                route_id SERIAL PRIMARY KEY,
                vehicle_id INTEGER NOT NULL,
                dc_id INTEGER,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                sequence INTEGER NOT NULL,
                distance_km NUMERIC NOT NULL,
                estimated_time NUMERIC NOT NULL,
                eta_days INTEGER,
                priority_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tracking_logs (
                id SERIAL PRIMARY KEY,
                vehicle_id INTEGER NOT NULL,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                timestamp TIMESTAMP NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logistics_metrics (
                metric_id SERIAL PRIMARY KEY,
                run_date DATE NOT NULL,
                total_distance_km NUMERIC NOT NULL,
                total_fuel_cost NUMERIC NOT NULL,
                total_co2_kg NUMERIC NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                sku_id INTEGER NOT NULL REFERENCES products(sku_id) ON DELETE CASCADE,
                store_id INTEGER NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
                sale_date DATE NOT NULL,
                quantity INTEGER NOT NULL
            );
        """)
        cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO walmart_user;")
        cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO walmart_user;")
        conn.commit()
        print("Database and tables created successfully")
    except Error as e:
        print(f"Error setting up database: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    setup_database()
