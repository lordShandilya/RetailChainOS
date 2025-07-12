
"""
seed_data.py
Purpose: Populates PostgreSQL tables for RetailChain OS, supporting walmart_db (SmartInventory, RouteAI, TrackX) and postgres (Fulfillment).
Execution: Run after db_setup.py.
Command: python app/smart_inventory/seed_data.py
"""
import psycopg2
from psycopg2 import Error
from datetime import datetime
from dotenv import dotenv_values
import bcrypt

ENV_VALUES = dotenv_values(".env")

DB_PARAMS = {
    "dbname": "walmart_db",
    "user": "walmart_user",
    "password": ENV_VALUES.get("DB_USER_PASSWORD", "securepassword"),
    "host": "localhost",
    "port": "5432"
}

def seed_data():
    """Populates tables with demo data."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        cur.execute("""
            TRUNCATE TABLE stores, products, inventory, forecasts, reorder_alerts,
            delivery_routes, tracking_logs, logistics_metrics, sales,
            FulfillmentCenter, InventoryItem
            RESTART IDENTITY CASCADE;
        """)
        conn.commit()

        # Seed FulfillmentCenter (moved first to satisfy inventory's foreign key)
        fulfillment_centers = [
            (1, 12.9716, 77.5946, 120, 500),  # Bengaluru
            (2, 28.7041, 77.1025, 80, 400),   # Delhi
            (3, 19.0760, 72.8777, 200, 600)   # Mumbai
        ]
        cur.executemany(
            "INSERT INTO FulfillmentCenter (id, latitude, longitude, current_workload, handling_capacity) VALUES (%s, %s, %s, %s, %s)",
            fulfillment_centers
        )

        # Seed stores
        stores = [
            (1, 'Bengaluru', '123 MG Road', 12.9716, 77.5946),
            (2, 'Chennai', '456 Anna Salai', 13.0827, 80.2707),
            (3, 'Hyderabad', '789 Banjara Hills', 17.3850, 78.4867),
            (4, 'Kochi', '101 Marine Drive', 9.9312, 76.2673),
            (5, 'Coimbatore', '202 Avinashi Road', 11.0168, 76.9558)
        ]
        cur.executemany(
            "INSERT INTO stores (store_id, store_location, store_address, lat, lng) VALUES (%s, %s, %s, %s, %s)",
            stores
        )

        # Seed vehicles
        cur.execute("""
            INSERT INTO vehicles (vehicle_id, capacity) VALUES
                (1, 1000), (2, 1500)
            ON CONFLICT (vehicle_id) DO NOTHING;
        """)

        # Seed users
        hashed_password = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute("""
            INSERT INTO users (username, password, role, store_id, vehicle_id)
            VALUES
                ('chennai_owner', %s, 'store_owner', 2, NULL),
                ('driver2', %s, 'delivery_partner', NULL, 2),
                ('admin', %s, 'admin', NULL, NULL)
            ON CONFLICT (username) DO NOTHING;
        """, (hashed_password, hashed_password, hashed_password))

        # Seed products
        products = [
            (1, 'Rice 5kg', 'Grocery'),
            (2, 'Oil 1L', 'Grocery'),
            (3, 'Dal 1kg', 'Grocery'),
            (4, 'Soap', 'Personal Care'),
            (5, 'Shampoo 200ml', 'Personal Care')
        ]
        cur.executemany(
            "INSERT INTO products (sku_id, name, category) VALUES (%s, %s, %s)",
            products
        )

        # Seed inventory
        inventory = [
            (1, 2, 1, 20), (1, 2, 2, 10), (1, 2, 3, 15), (1, 2, 4, 25), (1, 2, 5, 30),  # Chennai
            (1, 3, 1, 5), (1, 3, 2, 3), (1, 3, 3, 0), (1, 3, 4, 10), (1, 3, 5, 8),  # Hyderabad
            (1, 4, 1, 30), (1, 4, 2, 15), (1, 4, 3, 20), (1, 4, 4, 10), (1, 4, 5, 5),  # Kochi
            (1, 5, 1, 25), (1, 5, 2, 20), (1, 5, 3, 15), (1, 5, 4, 8), (1, 5, 5, 10)  # Coimbatore
        ]
        cur.executemany(
            "INSERT INTO inventory (dc_id, store_id, sku_id, current_stock) VALUES (%s, %s, %s, %s)",
            inventory
        )

        # Seed reorder_alerts
        reorder_alerts = [
            (2, 1, 20, 100, 0.9), (2, 2, 10, 50, 0.8), (2, 3, 15, 60, 0.7), (2, 4, 25, 50, 0.6), (2, 5, 30, 60, 0.5),  # Chennai
            (3, 1, 5, 150, 1.0), (3, 2, 3, 100, 0.95), (3, 3, 0, 120, 1.0), (3, 4, 10, 60, 0.9), (3, 5, 8, 80, 0.95),  # Hyderabad
            (4, 1, 30, 100, 0.85), (4, 2, 15, 50, 0.8), (4, 3, 20, 70, 0.75), (4, 4, 10, 40, 0.8), (4, 5, 5, 60, 0.9),  # Kochi
            (5, 1, 25, 90, 0.8), (5, 2, 20, 45, 0.75), (5, 3, 15, 65, 0.8), (5, 4, 8, 35, 0.85), (5, 5, 10, 55, 0.9)  # Coimbatore
        ]
        cur.executemany(
            "INSERT INTO reorder_alerts (store_id, sku_id, current_stock, reorder_threshold, priority_score) VALUES (%s, %s, %s, %s, %s)",
            reorder_alerts
        )

        # Seed delivery_routes
        delivery_routes = [
            (2, 1, 3, 1, 1, 460, 6.5, 1, 1.0),  # Bengaluru DC to Hyderabad
            (2, 1, 4, 1, 2, 350, 5.0, 1, 0.85),  # Bengaluru DC to Kochi
            (2, 1, 5, 1, 3, 50, 0.8, 1, 0.8),   # Kochi to Coimbatore
            (2, 1, 2, 1, 4, 280, 4.0, 2, 0.7)   # Coimbatore to Chennai
        ]
        cur.executemany(
            "INSERT INTO delivery_routes (vehicle_id, dc_id, store_id, sku_id, sequence, distance_km, estimated_time, eta_days, priority_score) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            delivery_routes
        )

        # Seed tracking_logs
        tracking_logs = [(2, 12.9716, 77.5946, datetime.now())]  # Start at Bengaluru DC
        cur.executemany(
            "INSERT INTO tracking_logs (vehicle_id, latitude, longitude, timestamp) VALUES (%s, %s, %s, %s)",
            tracking_logs
        )

        # Seed logistics_metrics
        cur.execute(
            "INSERT INTO logistics_metrics (run_date, total_distance_km, total_fuel_cost, total_co2_kg) VALUES (%s, %s, %s, %s)",
            (datetime.now().date(), 1140, 114, 228)  # Total: 460+350+50+280=1140km
        )

        # Seed sales
        sales = [
            (1, 2, '2025-07-01', 10), (1, 2, '2025-07-02', 15),  # Chennai: Rice
            (2, 2, '2025-07-01', 5), (2, 2, '2025-07-02', 8),    # Chennai: Oil
            (3, 2, '2025-07-01', 12), (3, 2, '2025-07-02', 20),  # Chennai: Dal
            (4, 2, '2025-07-01', 7), (4, 2, '2025-07-02', 9),    # Chennai: Soap
            (5, 2, '2025-07-01', 25), (5, 2, '2025-07-02', 30),  # Chennai: Shampoo
            (1, 3, '2025-07-01', 20), (1, 3, '2025-07-02', 25),  # Hyderabad: Rice
            (2, 3, '2025-07-01', 10), (2, 3, '2025-07-02', 12),  # Hyderabad: Oil
            (3, 3, '2025-07-01', 15), (3, 3, '2025-07-02', 18),  # Hyderabad: Dal
            (4, 3, '2025-07-01', 5), (4, 3, '2025-07-02', 7),    # Hyderabad: Soap
            (5, 3, '2025-07-01', 10), (5, 3, '2025-07-02', 12),  # Hyderabad: Shampoo
            (1, 4, '2025-07-01', 15), (1, 4, '2025-07-02', 20),  # Kochi: Rice
            (2, 4, '2025-07-01', 8), (2, 4, '2025-07-02', 10),   # Kochi: Oil
            (3, 4, '2025-07-01', 12), (3, 4, '2025-07-02', 15),  # Kochi: Dal
            (4, 4, '2025-07-01', 6), (4, 4, '2025-07-02', 8),    # Kochi: Soap
            (5, 4, '2025-07-01', 10), (5, 4, '2025-07-02', 12),  # Kochi: Shampoo
            (1, 5, '2025-07-01', 12), (1, 5, '2025-07-02', 18),  # Coimbatore: Rice
            (2, 5, '2025-07-01', 7), (2, 5, '2025-07-02', 9),    # Coimbatore: Oil
            (3, 5, '2025-07-01', 10), (3, 5, '2025-07-02', 13),  # Coimbatore: Dal
            (4, 5, '2025-07-01', 5), (4, 5, '2025-07-02', 7),    # Coimbatore: Soap
            (5, 5, '2025-07-01', 8), (5, 5, '2025-07-02', 10)    # Coimbatore: Shampoo
        ]
        cur.executemany(
            "INSERT INTO sales (sku_id, store_id, sale_date, quantity) VALUES (%s, %s, %s, %s)",
            sales
        )

        # Seed InventoryItem
        inventory_items = [
            (1, 'Rice 5kg', 500, 1), (2, 'Oil 1L', 200, 1), (3, 'Dal 1kg', 800, 1), (4, 'Soap', 600, 1), (5, 'Shampoo 200ml', 700, 1),  # Bengaluru
            (6, 'Rice 5kg', 300, 2), (7, 'Dal 1kg', 150, 2),  # Delhi
            (8, 'Oil 1L', 250, 3), (9, 'Soap', 500, 3)   # Mumbai
        ]
        cur.executemany(
            "INSERT INTO InventoryItem (id, sku, quantity, fulfillment_center_id) VALUES (%s, %s, %s, %s)",
            inventory_items
        )

        conn.commit()
        print("Data seeding completed successfully")
    except Error as e:
        print(f"Error seeding data: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    seed_data()
