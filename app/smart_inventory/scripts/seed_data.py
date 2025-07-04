#!/usr/bin/env python
"""
seed_data.py
Purpose: Populates PostgreSQL tables for RetailChain OS, simulating Walmart India's retail operations. Generates data for stores, products, sales, inventory, logistics, external factors, reorder alerts, delivery routes, and tracking logs.

Execution: Run after db_setup.py.
Command: python app/smart_inventory/seed_data.py
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
locations = [
    (1, 'Bengaluru', 'No. 123, Brigade Road, Bengaluru, Karnataka 560025', 12.9716, 77.5946),
    (2, 'Chennai', 'No. 180, Anna Salai, Chennai, Tamil Nadu 600002', 13.0827, 80.2707),
    (3, 'Hyderabad', 'Survey No. 64, Gachibowli, Hyderabad, Telangana 500032', 17.3850, 78.4867)
]
weather_options = ['Sunny', 'Cloudy', 'Rainy', 'Monsoon']
disruptions = ['None', 'Traffic', 'Strike']
start_date = datetime(2024, 6, 1)
end_date = datetime(2025, 6, 1)

def seed_data():
    """Populates all tables with mock data."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Clear existing data
        cur.execute("TRUNCATE TABLE sales, inventory, logistics, external_factors, products, reorder_alerts, delivery_routes, tracking_logs, stores RESTART IDENTITY CASCADE;")
        conn.commit()

        # Seed stores
        cur.executemany(
            "INSERT INTO stores (store_id, store_location, store_address, lat, lng) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            locations
        )
        conn.commit()

        # Seed products
        products = []
        for i in range(100):
            sku_id = i + 1
            name = fake.word().capitalize() + " " + fake.word().capitalize()
            category = random.choice(categories)
            price = round(random.uniform(10, 200), 2)
            store_id = random.choice(locations)[0]
            products.append((sku_id, name, category, price, store_id))
        cur.executemany(
            "INSERT INTO products (sku_id, name, category, price, store_id) VALUES (%s, %s, %s, %s, %s)",
            products
        )
        conn.commit()

        # Seed sales
        sales = []
        for product in products:
            sku_id, _, _, price, store_id = product
            current_date = start_date
            while current_date <= end_date:
                is_holiday = current_date.month in [10, 11] and random.random() < 0.1
                quantity = random.randint(10, 50) if is_holiday else random.randint(1, 20)
                revenue = quantity * price
                sales.append((sku_id, store_id, current_date.date(), quantity, revenue))
                current_date += timedelta(days=7)
        cur.executemany(
            "INSERT INTO sales (sku_id, store_id, sale_date, quantity, revenue) VALUES (%s, %s, %s, %s, %s)",
            sales
        )
        conn.commit()

        # Seed inventory
        inventory = []
        for product in products:
            sku_id, _, _, _, store_id = product
            stock_level = random.randint(5, 30)
            reorder_threshold = random.randint(50, 200)
            last_updated = end_date.date()
            inventory.append((sku_id, store_id, stock_level, reorder_threshold, last_updated))
        cur.executemany(
            "INSERT INTO inventory (sku_id, store_id, stock_level, reorder_threshold, last_updated) VALUES (%s, %s, %s, %s, %s)",
            inventory
        )
        conn.commit()

        # Seed reorder_alerts
        reorder_alerts = []
        for product in products:
            sku_id, _, _, _, store_id = product
            stock_level = random.randint(5, 30)
            reorder_threshold = random.randint(50, 200)
            if stock_level < reorder_threshold:
                priority_score = random.randint(10, 20)
                reorder_alerts.append((sku_id, store_id, stock_level, reorder_threshold, priority_score))
        cur.executemany(
            "INSERT INTO reorder_alerts (sku_id, store_id, current_stock, reorder_threshold, priority_score) VALUES (%s, %s, %s, %s, %s)",
            reorder_alerts
        )
        conn.commit()

        # Seed delivery_routes
        delivery_routes = []
        vehicle_id = 2
        origin = (0, 'Bengaluru DC', 'Walmart DC, Plot No. 50, NH44, Bengaluru, Karnataka 562157', 13.1000, 77.6000)
        for i, location in enumerate(locations):
            store_id, store_location, store_address, lat, lng = location
            distance_km = random.uniform(10, 340)
            estimated_time = distance_km / 40
            eta_days = max(1, int(estimated_time / 24))
            priority_score = random.randint(10, 20)
            delivery_routes.append((vehicle_id, 1, store_id, i, distance_km, estimated_time, eta_days, priority_score, lat, lng))
        cur.executemany(
            "INSERT INTO delivery_routes (vehicle_id, sku_id, store_id, sequence, distance_km, estimated_time, eta_days, priority_score, lat, lng) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            delivery_routes
        )
        conn.commit()

        # Seed tracking_logs
        tracking_logs = []
        for location in locations:
            _, _, _, lat, lng = location
            tracking_logs.append((vehicle_id, lat, lng, end_date))
        cur.executemany(
            "INSERT INTO tracking_logs (vehicle_id, latitude, longitude, timestamp) VALUES (%s, %s, %s, %s)",
            tracking_logs
        )
        conn.commit()

        # Seed logistics
        logistics = []
        for location in locations:
            store_id, _, store_address, _, _ = location
            logistics.append(('Walmart DC, Plot No. 50, NH44, Bengaluru, Karnataka 562157', store_address, random.uniform(10, 340), store_id))
        cur.executemany(
            "INSERT INTO logistics (origin, destination, distance_km, store_id) VALUES (%s, %s, %s, %s)",
            logistics
        )
        conn.commit()

        # Seed external factors
        external_factors = []
        for date in pd.date_range(start_date, end_date, freq='15D'):
            for store_id, store_location, _, _, _ in locations:
                weather = random.choice(weather_options)
                holiday = date.month in [10, 11] and random.random() < 0.1
                disruption = random.choice(disruptions)
                external_factors.append((date.date(), store_id, weather, holiday, disruption or 'None'))
        cur.executemany(
            "INSERT INTO external_factors (factor_date, store_id, weather, holiday, disruption) VALUES (%s, %s, %s, %s, %s)",
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
