#!/usr/bin/env python
"""
seed_data.py
Purpose: Populates PostgreSQL tables with realistic mock data for the SmartRetailSync project, simulating Walmart's
retail operations. Generates data for products, sales, inventory, logistics, and external factors.

Execution: Run after db_setup.py.
Command: python scripts/seed_data.py
Prerequisites: Install Faker (pip install Faker).
"""
import psycopg2
from psycopg2 import Error
from faker import Faker
import random
from datetime import datetime, timedelta
import pandas as pd

# Initialize Faker
fake = Faker()

# Database connection parameters
DB_PARAMS = {
    "dbname": "walmart_db",
    "user": "walmart_user",
    "password": "securepassword",
    "host": "localhost",
    "port": "5432"
}

# Data parameters
categories = ['Electronics', 'Apparel', 'Grocery', 'Home', 'Toys']
locations = ['New York', 'Dallas', 'Chicago', 'Houston', 'Atlanta']
weather_options = ['Sunny', 'Cloudy', 'Rainy', 'Snowy']
disruptions = ['None', 'Traffic', 'Strike']
start_date = datetime(2024, 6, 1)
end_date = datetime(2025, 6, 1)

def seed_data():
    """Populates all tables with mock data."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Clear existing data
        cur.execute("TRUNCATE TABLE sales, inventory, logistics, external_factors, products RESTART IDENTITY CASCADE;")
        conn.commit()

        # Seed products
        products = []
        for i in range(100):
            sku_id = i + 1
            name = fake.word().capitalize() + " " + fake.word().capitalize()
            category = random.choice(categories)
            price = round(random.uniform(10, 200), 2)
            store_location = random.choice(locations)
            products.append((sku_id, name, category, price, store_location))
        cur.executemany(
            "INSERT INTO products (sku_id, name, category, price, store_location) VALUES (%s, %s, %s, %s, %s)",
            products
        )
        conn.commit()

        # Seed sales
        sales = []
        for product in products:
            sku_id = product[0]
            current_date = start_date
            while current_date <= end_date:
                is_holiday = current_date.month in [11, 12] and random.random() < 0.1
                quantity = random.randint(10, 50) if is_holiday else random.randint(0, 20)
                revenue = quantity * product[3]
                sales.append((sku_id, current_date.date(), quantity, revenue))
                current_date += timedelta(days=7)
        cur.executemany(
            "INSERT INTO sales (sku_id, sale_date, quantity, revenue) VALUES (%s, %s, %s, %s)",
            sales
        )
        conn.commit()

        # Seed inventory
        inventory = []
        for product in products:
            sku_id = product[0]
            store_location = product[4]
            stock_level = random.randint(5, 30)  # Lowered for alerts
            last_updated = end_date.date()
            inventory.append((sku_id, store_location, stock_level, last_updated))
        cur.executemany(
            "INSERT INTO inventory (sku_id, store_location, stock_level, last_updated) VALUES (%s, %s, %s, %s)",
            inventory
        )
        conn.commit()

        # Seed logistics
        logistics = []
        depot = 'Atlanta'
        for _ in range(300):
            sku_id = random.randint(1, 100)
            destination = products[sku_id - 1][4]
            distance_km = round(random.uniform(100, 1000), 2)
            delivery_time = random.randint(6, 48)
            delivery_cost = round(distance_km * 0.3 + random.uniform(5, 15), 2)
            logistics.append((sku_id, depot, destination, delivery_time, distance_km, delivery_cost))
        cur.executemany(
            "INSERT INTO logistics (sku_id, origin, destination, delivery_time, distance_km, delivery_cost) VALUES (%s, %s, %s, %s, %s, %s)",
            logistics
        )
        conn.commit()

        # Seed external factors
        external_factors = []
        for date in pd.date_range(start_date, end_date, freq='15D'):
            for store in locations:
                weather = random.choice(weather_options)
                holiday = date.month in [11, 12] and random.random() < 0.1
                disruption = random.choice(disruptions)
                external_factors.append((date.date(), store, weather, holiday, disruption or 'None'))
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