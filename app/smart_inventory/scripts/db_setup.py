#!/usr/bin/env python
"""
db_setup.py
Purpose: Sets up PostgreSQL database and tables for RetailChain OS, simulating Walmart India's retail operations in southern India.

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

        # Drop and create walmart_db (uncomment if needed)
        cur.execute("DROP DATABASE IF EXISTS walmart_db;")
        cur.execute("CREATE DATABASE walmart_db OWNER walmart_user;")
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

        # Enable PostGIS in walmart_db (for future map support)
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.close()
        conn.close()

        # Connect to walmart_db as walmart_user for table creation
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Create stores table first
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

        # Create products table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price NUMERIC NOT NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)

        # Create sales table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                sale_id SERIAL PRIMARY KEY,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                sale_date DATE NOT NULL,
                quantity INTEGER NOT NULL,
                revenue NUMERIC NOT NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)

        # Create inventory table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                inventory_id SERIAL PRIMARY KEY,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                stock_level INTEGER NOT NULL,
                reorder_threshold INTEGER NOT NULL,
                last_updated DATE NOT NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)

        # Create logistics table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logistics (
                logistics_id SERIAL PRIMARY KEY,
                origin VARCHAR(255) NOT NULL,
                destination VARCHAR(255) NOT NULL,
                distance_km NUMERIC NOT NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)

        # Create external_factors table
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

        # Create forecasts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                forecast_id SERIAL PRIMARY KEY,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                forecast_date DATE NOT NULL,
                predicted_quantity NUMERIC NOT NULL,
                lower_bound NUMERIC NOT NULL,
                upper_bound NUMERIC NOT NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)

        # Create reorder_alerts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reorder_alerts (
                alert_id SERIAL PRIMARY KEY,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                current_stock INTEGER NOT NULL,
                reorder_threshold INTEGER NOT NULL,
                alert_date DATE NOT NULL DEFAULT CURRENT_DATE,
                priority_score FLOAT,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL
            );
        """)

        # Create delivery_routes table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS delivery_routes (
                route_id SERIAL PRIMARY KEY,
                vehicle_id INTEGER NOT NULL,
                sku_id INTEGER REFERENCES products(sku_id) ON DELETE SET NULL,
                store_id INTEGER REFERENCES stores(store_id) ON DELETE SET NULL,
                sequence INTEGER NOT NULL,
                distance_km NUMERIC NOT NULL,
                estimated_time NUMERIC NOT NULL,
                eta_days INTEGER,
                priority_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create tracking_logs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tracking_logs (
                id SERIAL PRIMARY KEY,
                vehicle_id INTEGER NOT NULL,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                timestamp TIMESTAMP NOT NULL
            );
        """)

        # Create logistics_metrics table
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

        # Grant permissions to walmart_user
        cur.execute("""
            GRANT ALL ON stores, products, sales, inventory, logistics, external_factors, forecasts,
                         reorder_alerts, delivery_routes, tracking_logs, logistics_metrics TO walmart_user;
        """)
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
