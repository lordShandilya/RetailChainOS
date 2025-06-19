
"""
seed_data.py
Purpose: Populates PostgreSQL tables with mock data to simulate Walmart's retail operations for the SmartRetailSync
project. This script generates realistic data for products, sales, inventory, logistics, and external factors, enabling
demand forecasting and last-mile optimization.

Why use this script:
- Creates realistic data with seasonality (e.g., holiday sales spikes) to mimic Walmart's retail patterns.
- Ensures foreign key constraints are respected by inserting products first.
- Uses Faker for randomized but plausible data, enhancing demo authenticity.
- Includes error handling and table truncation to prevent duplicates during development.

Execution: Run this script after db_setup.py to populate the database.
Command: python scripts/seed_data.py
"""

import pandas as pd
from faker import Faker
import psycopg2
from psycopg2 import Error
import random
from datetime import datetime

fake = Faker()

# Database connection parameters
DB_PARAMS = {
    "dbname": "walmart_db",
    "user": "walmart_user",
    "password": "securepassword",
    "host": "localhost",
    "port": "5432"
}

def seed_data():
    """Generates and inserts mock data into all tables."""
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Truncate tables to avoid duplicates (optional during development)
        cur.execute("TRUNCATE TABLE sales, inventory, logistics, external_factors, products RESTART IDENTITY CASCADE;")
        conn.commit()

        # Define constants
        categories = ["Electronics", "Groceries", "Clothing", "Home", "Toys"]
        locations = ["New York", "San Francisco", "Dallas", "Chicago", "Houston"]
        cities = ["Atlanta", "Seattle", "Boston", "Phoenix"]
        weather_options = ["Sunny", "Rainy", "Cloudy", "Snowy"]
        disruptions = ["None", "Port Delay", "Strike", "Flood", "Fuel Shortage"]

        # Seed products
        # Purpose: Creates 100 SKUs with realistic names, categories, and prices
        products = [
            (fake.word().capitalize() + " Product", random.choice(categories), round(random.uniform(10, 300), 2), random.choice(locations))
            for _ in range(100)
        ]
        cur.executemany(
            "INSERT INTO products (name, category, price, store_location) VALUES (%s, %s, %s, %s)",
            products
        )
        conn.commit()

        # Seed sales
        # Purpose: Generates weekly sales data for 1 year with holiday seasonality
        start_date = datetime(2023, 6, 1)
        end_date = datetime(2024, 6, 1)
        date_range = pd.date_range(start_date, end_date, freq='7D')
        sales = []
        for sku_id in range(1, 101):
            for date in date_range:
                month = date.month
                qty = random.randint(10, 50) if month in [11, 12] else random.randint(0, 20)
                price = products[sku_id - 1][2]
                revenue = round(qty * price, 2)
                sales.append((sku_id, date, qty, revenue))
        cur.executemany(
            "INSERT INTO sales (sku_id, sale_date, quantity, revenue) VALUES (%s, %s, %s, %s)",
            sales
        )
        conn.commit()

        # Seed inventory
        # Purpose: Sets initial stock levels for each SKU at its store location
        inventory = []
        for sku_id in range(1, 101):
            store = products[sku_id - 1][3]
            stock_level = random.randint(50, 300)
            last_updated = datetime.now().date()
            inventory.append((sku_id, store, stock_level, last_updated))
        cur.executemany(
            "INSERT INTO inventory (sku_id, store_location, stock_level, last_updated) VALUES (%s, %s, %s, %s)",
            inventory
        )
        conn.commit()

        # Seed logistics
        # Purpose: Simulates last-mile delivery data for route optimization
        logistics = []
        for _ in range(300):
            sku_id = random.randint(1, 100)
            origin = random.choice(cities)
            destination = products[sku_id - 1][3]
            distance_km = round(random.uniform(50.0, 500.0), 2)
            delivery_time = random.randint(6, 48)
            delivery_cost = round(distance_km * 0.3 + random.uniform(5, 15), 2)
            logistics.append((sku_id, origin, destination, delivery_time, distance_km, delivery_cost))
        cur.executemany(
            "INSERT INTO logistics (sku_id, origin, destination, delivery_time, distance_km, delivery_cost) VALUES (%s, %s, %s, %s, %s, %s)",
            logistics
        )
        conn.commit()

        # Seed external factors
        # Purpose: Provides external influences for demand forecasting
        external_factors = []
        for date in pd.date_range(start_date, end_date, freq='15D'):
            for store in locations:
                weather = random.choice(weather_options)
                holiday = random.choice([True, False]) if date.month in [11, 12] else False
                disruption = random.choice(disruptions)
                external_factors.append((date.date(), store, weather, holiday, disruption))
        cur.executemany(
            "INSERT INTO external_factors (factor_date, store_location, weather, holiday, disruption) VALUES (%s, %s, %s, %s, %s)",
            external_factors
        )
        conn.commit()

        print("Data seeding completed successfully")

    except Error as e:
        print(f"Error seeding data: {e}")
        conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    seed_data()
