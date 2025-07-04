#!/usr/bin/env python
"""
db_setup.py
Purpose: Sets up PostgreSQL database and tables for the SmartRetailSync project, simulating Walmart India's retail operations.

Execution: Run before seed_data.py.
Command: python app/smart_inventory/db_setup.py
"""
import psycopg2
from psycopg2 import Error

DB_PARAMS = {
    "dbname": "walmart_db",
    "user": "walmart_user",
    "password": "securepassword",
    "host": "localhost",
    "port": "5432"
}

POSTGRES_PARAMS = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "postgres",  # Replace with your postgres user password
    "host": "localhost",
    "port": "5432"
}

def setup_database():
    """Creates database and tables."""
    try:
        # Connect to default database as postgres to create walmart_db
        conn = psycopg2.connect(**POSTGRES_PARAMS)
        conn.autocommit = True
        cur = conn.cursor()

        # Ensure walmart_user exists and has CREATEDB privilege
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'walmart_user';")
        if cur.fetchone() is None:
            cur.execute("CREATE USER walmart_user WITH PASSWORD 'securepassword';")
        cur.execute("ALTER USER walmart_user WITH CREATEDB;")

        # Drop and create walmart_db
        # cur.execute("DROP DATABASE IF EXISTS walmart_db;")
        # cur.execute("CREATE DATABASE walmart_db OWNER walmart_user;")
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

        # Enable PostGIS in walmart_db
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.close()
        conn.close()

        # Connect to walmart_db as walmart_user for table creation
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Create tablesNOT
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price NUMERIC NOT NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                sale_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id),
                sale_date DATE NOT NULL,
                quantity INT NOT NULL,
                revenue NUMERIC NOT NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                inventory_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id),
                stock_level INT NOT NULL,
                last_updated DATE NOT NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logistics (
                origin VARCHAR(255),
                destination VARCHAR(255),
                distance_km FLOAT,
                lat FLOAT,
                lng FLOAT,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS external_factors (
                factor_id SERIAL PRIMARY KEY,
                factor_date DATE NOT NULL,
                weather TEXT,
                holiday BOOLEAN,
                disruption TEXT,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                forecast_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id),
                forecast_date DATE NOT NULL,
                predicted_quantity NUMERIC NOT NULL,
                lower_bound NUMERIC NOT NULL,
                upper_bound NUMERIC NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reorder_alerts (
                alert_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id),
                reorder_threshold NUMERIC NOT NULL,
                current_stock INT NOT NULL,
                alert_date DATE NOT NULL,
                priority_score FLOAT,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS delivery_routes (
                route_id SERIAL PRIMARY KEY,
                vehicle_id INT NOT NULL,
                sku_id INT REFERENCES products(sku_id),
                sequence INT NOT NULL,
                distance_km NUMERIC NOT NULL,
                estimated_time NUMERIC NOT NULL,
                priority_score FLOAT,
                eta_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tracking_logs (
                id SERIAL PRIMARY KEY,
                vehicle_id INTEGER,
                latitude FLOAT,
                longitude FLOAT,
                timestamp TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS osm_roads (
                id SERIAL PRIMARY KEY,
                geom GEOMETRY(LINESTRING, 4326),
                name TEXT,
                highway TEXT
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

        # store location relation
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
