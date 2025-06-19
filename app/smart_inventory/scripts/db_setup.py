
"""
db_setup.py
Purpose: Creates PostgreSQL tables for the SmartRetailSync project, ensuring a robust schema for inventory management,
demand forecasting, and logistics optimization. This script is the first step in setting up the database for Walmart's
retail supply chain simulation, aligning with their need for scalable, data-driven operations.

Why use this script:
- Defines tables with foreign key constraints to maintain data integrity (e.g., sales linked to products).
- Uses 'IF NOT EXISTS' to avoid errors if tables already exist, making it safe for repeated runs.
- Separates schema creation from data seeding for modularity and clarity, critical for hackathon maintainability.

Execution: Run this script first to initialize the database schema.
Command: python scripts/db_setup.py
"""


"""
Note:- To let this script work on your system you first need to install postgresql and then you have to grant all the priviliges (aka permissions)
to the "walmart_user" as throughout the project we will use this user to get things done from our database

CREATE DATABASE walmart_db;
CREATE USER walmart_user WITH PASSWORD 'securepassword';
GRANT ALL PRIVILEGES ON DATABASE walmart_db TO walmart_user;

ALTER DATABASE walmart_db OWNER TO walmart_user;

Make sure to run above commands !!! (By Sahitya)

## How to login (for Ubuntu or wsl2)
-> sudo -u postgres psql

"""

import psycopg2
from psycopg2 import Error

# Database connection parameters
DB_PARAMS = {
    "dbname": "walmart_db",
    "user": "walmart_user",
    "password": "securepassword",
    "host": "localhost",
    "port": "5432"
}

def create_tables():
    """Creates all required tables with appropriate schema and constraints."""
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Create products table
        # Purpose: Stores SKU details, central to Walmart's inventory system
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price NUMERIC NOT NULL CHECK (price >= 0),
                store_location TEXT NOT NULL
            );
        """)

        # Create sales table
        # Purpose: Tracks historical sales for demand forecasting, critical for predicting future demand
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id) ON DELETE CASCADE,
                sale_date DATE NOT NULL,
                quantity INT NOT NULL CHECK (quantity >= 0),
                revenue NUMERIC NOT NULL CHECK (revenue >= 0)
            );
        """)

        # Create inventory table
        # Purpose: Monitors current stock levels per store, enabling real-time inventory tracking
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                sku_id INT REFERENCES products(sku_id) ON DELETE CASCADE,
                store_location TEXT NOT NULL,
                stock_level INT NOT NULL CHECK (stock_level >= 0),
                last_updated DATE NOT NULL,
                PRIMARY KEY (sku_id, store_location)
            );
        """)

        # Create logistics table
        # Purpose: Stores delivery data for last-mile optimization, aligning with Walmart's logistics focus
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logistics (
                delivery_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id) ON DELETE CASCADE,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                delivery_time INT NOT NULL CHECK (delivery_time >= 0), -- in hours
                distance_km FLOAT NOT NULL CHECK (distance_km >= 0),
                delivery_cost NUMERIC NOT NULL CHECK (delivery_cost >= 0)
            );
        """)

        # Create external_factors table
        # Purpose: Captures external influences (e.g., holidays) for accurate demand forecasting
        cur.execute("""
            CREATE TABLE IF NOT EXISTS external_factors (
                factor_date DATE NOT NULL,
                store_location TEXT NOT NULL,
                weather TEXT NOT NULL,
                holiday BOOLEAN NOT NULL,
                disruption TEXT NOT NULL,
                PRIMARY KEY (factor_date, store_location)
            );
        """)

        # Create forecasts table
        # Purpose: Stores demand predictions, enabling inventory planning and dashboard visualization
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                forecast_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id) ON DELETE CASCADE,
                forecast_date DATE NOT NULL,
                predicted_quantity FLOAT NOT NULL,
                lower_bound FLOAT NOT NULL,
                upper_bound FLOAT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create reorder_alerts table
        # Purpose: Generates actionable alerts for low stock, directly addressing Walmart's inventory efficiency
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reorder_alerts (
                alert_id SERIAL PRIMARY KEY,
                sku_id INT REFERENCES products(sku_id) ON DELETE CASCADE,
                store_location TEXT NOT NULL,
                reorder_threshold FLOAT NOT NULL,
                current_stock INT NOT NULL,
                alert_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Commit changes
        conn.commit()
        print("Tables created successfully")

    except Error as e:
        print(f"Error creating tables: {e}")
        conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    create_tables()
