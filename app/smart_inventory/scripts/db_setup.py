#!/usr/bin/env python
"""
db_setup.py
Purpose: Sets up PostgreSQL database and tables for the SmartRetailSync project, simulating Walmart's retail operations.

Execution: Run before seed_data.py.
Command: python scripts/db_setup.py
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

def setup_database():
    """Creates database and tables."""
    try:
        # Connect to default database
        conn = psycopg2.connect(
            dbname="postgres",
            user=DB_PARAMS["user"],
            password=DB_PARAMS["password"],
            host=DB_PARAMS["host"],
            port=DB_PARAMS["port"]
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Create database
        cur.execute("DROP DATABASE IF EXISTS walmart_db;")
        cur.execute("CREATE DATABASE walmart_db;")
        cur.close()
        conn.close()

        # Connect to walmart_db
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Create tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price NUMERIC NOT NULL,
                store_location TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                sale_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id),
                sale_date DATE NOT NULL,
                quantity INT NOT NULL,
                revenue NUMERIC NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                inventory_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id),
                store_location TEXT NOT NULL,
                stock_level INT NOT NULL,
                last_updated DATE NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logistics (
                logistics_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id),
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                delivery_time INT NOT NULL,
                distance_km NUMERIC NOT NULL,
                delivery_cost NUMERIC NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS external_factors (
                factor_id SERIAL PRIMARY KEY,
                factor_date DATE NOT NULL,
                store_location TEXT NOT NULL,
                weather TEXT,
                holiday BOOLEAN,
                disruption TEXT
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
                store_location TEXT NOT NULL,
                reorder_threshold NUMERIC NOT NULL,
                current_stock INT NOT NULL,
                alert_date DATE NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS delivery_routes (
                route_id SERIAL PRIMARY KEY,
                vehicle_id INT NOT NULL,
                sku_id INT REFERENCES products(sku_id),
                store_location TEXT NOT NULL,
                sequence INT NOT NULL,
                distance_km NUMERIC NOT NULL,
                estimated_time INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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