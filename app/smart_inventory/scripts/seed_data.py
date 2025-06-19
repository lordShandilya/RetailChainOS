
import pandas as pd
from faker import Faker
import psycopg2
import random
from datetime import datetime

fake = Faker()

# Connect to PostgreSQL
try:
    conn = psycopg2.connect(
        dbname="walmart_db",
        user="walmart_user",
        password="securepassword",
        host="localhost",
        port="5432"
    )
    cur = conn.cursor()
except Exception as e:
    print(f"Database connection failed: {e}")
    exit()

# Create tables
try:
    # Products table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            sku_id SERIAL PRIMARY KEY,
            name TEXT,
            category TEXT,
            price NUMERIC,
            store_location TEXT
        );
    """)

    # Sales table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            sku_id INT REFERENCES products(sku_id),
            sale_date DATE,
            quantity INT,
            revenue NUMERIC
        );
    """)

    # Inventory table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            sku_id INT REFERENCES products(sku_id),
            store_location TEXT,
            stock_level INT,
            last_updated DATE
        );
    """)

    # Logistics table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logistics (
            delivery_id SERIAL PRIMARY KEY,
            sku_id INT REFERENCES products(sku_id),
            origin TEXT,
            destination TEXT,
            delivery_time INT,  -- in hours
            distance_km FLOAT,
            delivery_cost NUMERIC
        );
    """)

    # External factors table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS external_factors (
            factor_date DATE,
            store_location TEXT,
            weather TEXT,
            holiday BOOLEAN,
            disruption TEXT
        );
    """)
except Exception as e:
    print(f"Table creation failed: {e}")
    conn.close()
    exit()

# Clear tables to avoid duplicates (optional, comment out if you want to keep existing data)
cur.execute("TRUNCATE TABLE sales, inventory, logistics, external_factors, products RESTART IDENTITY CASCADE;")

# Generate fake data
categories = ["Electronics", "Groceries", "Clothing", "Home", "Toys"]
locations = ["New York", "San Francisco", "Dallas", "Chicago", "Houston"]  # Walmart-like store locations
cities = ["Atlanta", "Seattle", "Boston", "Phoenix"]  # Warehouse cities

# Products
products = [
    (fake.word().capitalize() + " Product", random.choice(categories), round(random.uniform(10, 300), 2), random.choice(locations))
    for _ in range(100)
]
try:
    cur.executemany(
        "INSERT INTO products (name, category, price, store_location) VALUES (%s, %s, %s, %s)",
        products
    )
except Exception as e:
    print(f"Products insert failed: {e}")
    conn.close()
    exit()

# Sales data (with seasonality for realism)
start_date = datetime(2023, 6, 1)
end_date = datetime(2024, 6, 1)
date_range = pd.date_range(start_date, end_date, freq='7D')  # Weekly sales

sales = []
for sku_id in range(1, 101):
    for date in date_range:
        # Add seasonality: higher sales in November/December (holiday season)
        month = date.month
        qty = random.randint(10, 50) if month in [11, 12] else random.randint(0, 20)
        price = products[sku_id - 1][2]  # Use product price
        revenue = round(qty * price, 2)
        sales.append((sku_id, date, qty, revenue))

try:
    cur.executemany(
        "INSERT INTO sales (sku_id, sale_date, quantity, revenue) VALUES (%s, %s, %s, %s)",
        sales
    )
except Exception as e:
    print(f"Sales insert failed: {e}")
    conn.close()
    exit()

# Inventory data
inventory = []
for sku_id in range(1, 101):
    store = products[sku_id - 1][3]  # Store location from products
    stock_level = random.randint(50, 300)
    last_updated = datetime.now().date()
    inventory.append((sku_id, store, stock_level, last_updated))

try:
    cur.executemany(
        "INSERT INTO inventory (sku_id, store_location, stock_level, last_updated) VALUES (%s, %s, %s, %s)",
        inventory
    )
except Exception as e:
    print(f"Inventory insert failed: {e}")
    conn.close()
    exit()

# Logistics data
logistics = []
for _ in range(300):
    sku_id = random.randint(1, 100)
    origin = random.choice(cities)
    destination = products[sku_id - 1][3]  # Destination = store_location
    distance_km = round(random.uniform(50.0, 500.0), 2)  # Realistic distances for Walmart’s network
    delivery_time = random.randint(6, 48)  # Shorter delivery times for last-mile
    delivery_cost = round(distance_km * 0.3 + random.uniform(5, 15), 2)  # Adjusted cost
    logistics.append((sku_id, origin, destination, delivery_time, distance_km, delivery_cost))

try:
    cur.executemany(
        "INSERT INTO logistics (sku_id, origin, destination, delivery_time, distance_km, delivery_cost) VALUES (%s, %s, %s, %s, %s, %s)",
        logistics
    )
except Exception as e:
    print(f"Logistics insert failed: {e}")
    conn.close()
    exit()

# External factors
weather_options = ["Sunny", "Rainy", "Cloudy", "Snowy"]
disruptions = ["None", "Port Delay", "Strike", "Flood", "Fuel Shortage"]
external_factors = []
for date in pd.date_range(start_date, end_date, freq='15D'):
    for store in locations:  # Use defined locations
        weather = random.choice(weather_options)
        holiday = random.choice([True, False]) if date.month in [11, 12] else False  # Holidays in Nov/Dec
        disruption = random.choice(disruptions)
        external_factors.append((date.date(), store, weather, holiday, disruption))

try:
    cur.executemany(
        "INSERT INTO external_factors (factor_date, store_location, weather, holiday, disruption) VALUES (%s, %s, %s, %s, %s)",
        external_factors
    )
except Exception as e:
    print(f"External factors insert failed: {e}")
    conn.close()
    exit()

# Commit and close
conn.commit()
cur.close()
conn.close()

print("Seeding of data completed successfully")



# Database creation scripts (SQL)

# CREATE USER walmart_user WITH PASSWORD 'securepassword';
# CREATE DATABASE walmart_db;
# GRANT ALL PRIVILEGES ON DATABASE walmart_db TO walmart_user;




############################################## context

# let the grok also check this seeding process and if he wants to modify something then he can?
