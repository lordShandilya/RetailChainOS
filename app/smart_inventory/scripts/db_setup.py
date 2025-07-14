"""
db_setup.py
Purpose: Creates PostgreSQL databases and tables for RetailChain OS, supporting walmart_db (SmartInventory, RouteAI, TrackX) and postgres (Fulfillment).
Execution: Run before seed_data.py.
Command: python app/smart_inventory/db_setup.py
"""
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import dotenv_values

ENV_VALUES = dotenv_values(".env")

def create_databases():
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="walmart_user",
            password=ENV_VALUES.get("DB_USER_PASSWORD", "securepassword"),
            host="localhost",
            port="5432"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("DROP DATABASE IF EXISTS walmart_db")
        cur.execute("CREATE DATABASE walmart_db OWNER walmart_user")
        print("walmart_db created successfully")
    except Exception as e:
        print(f"Error creating databases: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def create_tables():
    try:
        conn = psycopg2.connect(
            dbname="walmart_db",
            user="walmart_user",
            password=ENV_VALUES.get("DB_USER_PASSWORD", "securepassword"),
            host="localhost",
            port="5432"
        )
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                store_id SERIAL PRIMARY KEY,
                store_location VARCHAR(100) NOT NULL,
                store_address VARCHAR(255),
                lat FLOAT,
                lng FLOAT,
                verified BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS FulfillmentCenter (
                id SERIAL PRIMARY KEY,
                latitude FLOAT,
                longitude FLOAT,
                current_workload INTEGER,
                handling_capacity INTEGER
            );

            CREATE TABLE IF NOT EXISTS products (
                sku_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                category VARCHAR(50)
            );

            CREATE TABLE IF NOT EXISTS inventory (
                dc_id INTEGER,
                store_id INTEGER,
                sku_id INTEGER NOT NULL,
                current_stock INTEGER NOT NULL,
                PRIMARY KEY (dc_id, store_id, sku_id),
                FOREIGN KEY (dc_id) REFERENCES FulfillmentCenter(id) ON DELETE SET NULL,
                FOREIGN KEY (store_id) REFERENCES stores(store_id) ON DELETE SET NULL,
                FOREIGN KEY (sku_id) REFERENCES products(sku_id)
            );

            CREATE TABLE IF NOT EXISTS forecasts (
                store_id INTEGER,
                sku_id INTEGER,
                predicted_demand INTEGER NOT NULL,
                PRIMARY KEY (store_id, sku_id),
                FOREIGN KEY (store_id) REFERENCES stores(store_id),
                FOREIGN KEY (sku_id) REFERENCES products(sku_id)
            );

            CREATE TABLE IF NOT EXISTS reorder_alerts (
                store_id INTEGER,
                sku_id INTEGER,
                current_stock INTEGER NOT NULL,
                reorder_threshold INTEGER NOT NULL,
                priority_score FLOAT,
                PRIMARY KEY (store_id, sku_id),
                FOREIGN KEY (store_id) REFERENCES stores(store_id),
                FOREIGN KEY (sku_id) REFERENCES products(sku_id)
            );

            CREATE TABLE IF NOT EXISTS vehicles (
                vehicle_id SERIAL PRIMARY KEY,
                capacity INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(50) PRIMARY KEY,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                store_id INTEGER,
                vehicle_id INTEGER,
                FOREIGN KEY (store_id) REFERENCES stores(store_id),
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
            );

            CREATE TABLE IF NOT EXISTS delivery_routes (
                route_id SERIAL PRIMARY KEY,
                vehicle_id INTEGER,
                dc_id INTEGER,
                store_id INTEGER,
                sku_id INTEGER,
                sequence INTEGER,
                distance_km FLOAT,
                estimated_time FLOAT,
                eta_days INTEGER,
                priority_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
                FOREIGN KEY (dc_id) REFERENCES FulfillmentCenter(id),
                FOREIGN KEY (store_id) REFERENCES stores(store_id),
                FOREIGN KEY (sku_id) REFERENCES products(sku_id)
            );

            CREATE TABLE IF NOT EXISTS tracking_logs (
                log_id SERIAL PRIMARY KEY,
                vehicle_id INTEGER,
                latitude FLOAT,
                longitude FLOAT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
            );

            CREATE TABLE IF NOT EXISTS logistics_metrics (
                metric_id SERIAL PRIMARY KEY,
                run_date DATE,
                total_distance_km FLOAT,
                total_fuel_cost FLOAT,
                total_co2_kg FLOAT
            );

            CREATE TABLE IF NOT EXISTS sales (
                sale_id SERIAL PRIMARY KEY,
                sku_id INTEGER,
                store_id INTEGER,
                sale_date DATE,
                quantity INTEGER,
                FOREIGN KEY (sku_id) REFERENCES products(sku_id),
                FOREIGN KEY (store_id) REFERENCES stores(store_id)
            );

            CREATE TABLE IF NOT EXISTS InventoryItem (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(100),
                quantity INTEGER,
                fulfillment_center_id INTEGER,
                FOREIGN KEY (fulfillment_center_id) REFERENCES FulfillmentCenter(id)
            );
        """)

        conn.commit()
        print("Tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    create_databases()
    create_tables()
