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
            FulfillmentCenter, InventoryItem, vehicles, users
            RESTART IDENTITY CASCADE;
        """)
        conn.commit()

        # Seed FulfillmentCenter
        fulfillment_centers = [
            (1, 12.9716, 77.5946, 120, 500),  # Bengaluru DC
            (2, 28.7041, 77.1025, 80, 400),   # Delhi DC
            (3, 19.0760, 72.8777, 200, 600)   # Mumbai DC
        ]
        cur.executemany(
            "INSERT INTO FulfillmentCenter (id, latitude, longitude, current_workload, handling_capacity) VALUES (%s, %s, %s, %s, %s)",
            fulfillment_centers
        )

        # Seed stores (7 stores)
        stores = [
            (1, 'Bengaluru', '123 MG Road', 12.9716, 77.5946),
            (2, 'Chennai', '456 Anna Salai', 13.0827, 80.2707),
            (3, 'Hyderabad', '789 Banjara Hills', 17.3850, 78.4867),
            (4, 'Kochi', '101 Marine Drive', 9.9312, 76.2673),
            (5, 'Coimbatore', '202 Avinashi Road', 11.0168, 76.9558),
            (6, 'Delhi', '303 Connaught Place', 28.7041, 77.1025),
            (7, 'Mumbai', '404 Marine Drive', 19.0760, 72.8777)
        ]
        cur.executemany(
            "INSERT INTO stores (store_id, store_location, store_address, lat, lng) VALUES (%s, %s, %s, %s, %s)",
            stores
        )

        # Seed vehicles
        cur.execute("""
            INSERT INTO vehicles (vehicle_id, capacity) VALUES
                (1, 1000), (2, 1500), (3, 1200), (4, 800)
            ON CONFLICT (vehicle_id) DO NOTHING;
        """)

        # Seed users
        hashed_password = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute("""
            INSERT INTO users (username, password, role, store_id, vehicle_id)
            VALUES
                ('bengaluru_owner', %s, 'store_owner', 1, NULL),
                ('chennai_owner', %s, 'store_owner', 2, NULL),
                ('hyderabad_owner', %s, 'store_owner', 3, NULL),
                ('kochi_owner', %s, 'store_owner', 4, NULL),
                ('coimbatore_owner', %s, 'store_owner', 5, NULL),
                ('delhi_owner', %s, 'store_owner', 6, NULL),
                ('mumbai_owner', %s, 'store_owner', 7, NULL),
                ('driver1', %s, 'delivery_partner', NULL, 1),
                ('driver2', %s, 'delivery_partner', NULL, 2),
                ('driver3', %s, 'delivery_partner', NULL, 3),
                ('driver4', %s, 'delivery_partner', NULL, 4),
                ('admin', %s, 'admin', NULL, NULL)
            ON CONFLICT (username) DO NOTHING;
        """, (hashed_password,) * 12)

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

        # Seed inventory (distributed across 3 DCs)
        inventory = [
            # Bengaluru DC (dc_id=1) serves Bengaluru, Hyderabad, Chennai
            (1, 1, 1, 25), (1, 1, 2, 15), (1, 1, 3, 20), (1, 1, 4, 30), (1, 1, 5, 10),
            (1, 3, 1, 5), (1, 3, 2, 3), (1, 3, 3, 0), (1, 3, 4, 10), (1, 3, 5, 8),
            (1, 2, 1, 20), (1, 2, 2, 10), (1, 2, 3, 15), (1, 2, 4, 25), (1, 2, 5, 30),
            # Mumbai DC (dc_id=3) serves Kochi, Coimbatore, Mumbai
            (3, 4, 1, 30), (3, 4, 2, 15), (3, 4, 3, 20), (3, 4, 4, 10), (3, 4, 5, 5),
            (3, 5, 1, 25), (3, 5, 2, 20), (3, 5, 3, 15), (3, 5, 4, 8), (3, 5, 5, 10),
            (3, 7, 1, 15), (3, 7, 2, 10), (3, 7, 3, 12), (3, 7, 4, 20), (3, 7, 5, 25),
            # Delhi DC (dc_id=2) serves Delhi
            (2, 6, 1, 20), (2, 6, 2, 12), (2, 6, 3, 18), (2, 6, 4, 15), (2, 6, 5, 22)
        ]
        cur.executemany(
            "INSERT INTO inventory (dc_id, store_id, sku_id, current_stock) VALUES (%s, %s, %s, %s)",
            inventory
        )

        # Seed reorder_alerts
        reorder_alerts = [
            # Bengaluru DC stores
            (1, 1, 25, 80, 0.8), (1, 2, 15, 50, 0.7), (1, 3, 20, 60, 0.75), (1, 4, 30, 70, 0.6), (1, 5, 10, 50, 0.8),
            (3, 1, 5, 100, 0.95), (3, 2, 3, 80, 0.9), (3, 3, 0, 90, 1.0), (3, 4, 10, 60, 0.85), (3, 5, 8, 70, 0.9),
            (2, 1, 20, 90, 0.85), (2, 2, 10, 60, 0.8), (2, 3, 15, 70, 0.75), (2, 4, 25, 80, 0.7), (2, 5, 30, 90, 0.65),
            # Mumbai DC stores
            (4, 1, 30, 100, 0.85), (4, 2, 15, 50, 0.8), (4, 3, 20, 70, 0.75), (4, 4, 10, 40, 0.8), (4, 5, 5, 60, 0.9),
            (5, 1, 25, 90, 0.8), (5, 2, 20, 45, 0.75), (5, 3, 15, 65, 0.8), (5, 4, 8, 35, 0.85), (5, 5, 10, 55, 0.9),
            (7, 1, 15, 80, 0.75), (7, 2, 10, 50, 0.8), (7, 3, 12, 60, 0.8), (7, 4, 20, 70, 0.75), (7, 5, 25, 80, 0.7),
            # Delhi DC store
            (6, 1, 20, 90, 0.8), (6, 2, 12, 50, 0.75), (6, 3, 18, 60, 0.7), (6, 4, 15, 50, 0.75), (6, 5, 22, 70, 0.7)
        ]
        cur.executemany(
            "INSERT INTO reorder_alerts (store_id, sku_id, current_stock, reorder_threshold, priority_score) VALUES (%s, %s, %s, %s, %s)",
            reorder_alerts
        )

        # Seed delivery_routes
        delivery_routes = [
            # Vehicle 1: Bengaluru DC -> Bengaluru -> Hyderabad -> Chennai
            (1, 1, 1, 1, 1, 0, 0, 1, 1.0),    # Bengaluru DC to Bengaluru
            (1, 1, 3, 1, 2, 460, 6.5, 1, 0.9), # Bengaluru to Hyderabad
            (1, 1, 2, 1, 3, 680, 9.5, 2, 0.8), # Hyderabad to Chennai
            # Vehicle 2: Mumbai DC -> Kochi -> Coimbatore -> Chennai
            (2, 3, 4, 1, 1, 920, 13.0, 2, 0.85), # Mumbai DC to Kochi
            (2, 3, 5, 1, 2, 50, 0.8, 1, 0.8),   # Kochi to Coimbatore
            (2, 3, 2, 1, 3, 280, 4.0, 2, 0.75), # Coimbatore to Chennai
            # Vehicle 3: Delhi DC -> Delhi
            (3, 2, 6, 1, 1, 0, 0, 1, 1.0),     # Delhi DC to Delhi
            # Vehicle 4: Mumbai DC -> Mumbai
            (4, 3, 7, 1, 1, 0, 0, 1, 1.0)      # Mumbai DC to Mumbai
        ]
        cur.executemany(
            "INSERT INTO delivery_routes (vehicle_id, dc_id, store_id, sku_id, sequence, distance_km, estimated_time, eta_days, priority_score) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            delivery_routes
        )

        # Seed tracking_logs
        tracking_logs = [
            (1, 12.9716, 77.5946, datetime.now()),  # Vehicle 1: Bengaluru DC
            (2, 19.0760, 72.8777, datetime.now()),  # Vehicle 2: Mumbai DC
            (3, 28.7041, 77.1025, datetime.now()),  # Vehicle 3: Delhi DC
            (4, 19.0760, 72.8777, datetime.now())   # Vehicle 4: Mumbai DC
        ]
        cur.executemany(
            "INSERT INTO tracking_logs (vehicle_id, latitude, longitude, timestamp) VALUES (%s, %s, %s, %s)",
            tracking_logs
        )

        # Seed logistics_metrics
        cur.execute(
            "INSERT INTO logistics_metrics (run_date, total_distance_km, total_fuel_cost, total_co2_kg) VALUES (%s, %s, %s, %s)",
            (datetime.now().date(), 1418, 141.8, 283.6)  # Total: 460+680+920+50+280=2398km
        )

        # Seed sales
        sales = [
            # Bengaluru
            (1, 1, '2025-07-01', 12), (1, 1, '2025-07-02', 15),
            (2, 1, '2025-07-01', 8), (2, 1, '2025-07-02', 10),
            (3, 1, '2025-07-01', 10), (3, 1, '2025-07-02', 12),
            (4, 1, '2025-07-01', 15), (4, 1, '2025-07-02', 18),
            (5, 1, '2025-07-01', 7), (5, 1, '2025-07-02', 9),
            # Chennai
            (1, 2, '2025-07-01', 10), (1, 2, '2025-07-02', 15),
            (2, 2, '2025-07-01', 5), (2, 2, '2025-07-02', 8),
            (3, 2, '2025-07-01', 12), (3, 2, '2025-07-02', 20),
            (4, 2, '2025-07-01', 7), (4, 2, '2025-07-02', 9),
            (5, 2, '2025-07-01', 25), (5, 2, '2025-07-02', 30),
            # Hyderabad
            (1, 3, '2025-07-01', 20), (1, 3, '2025-07-02', 25),
            (2, 3, '2025-07-01', 10), (2, 3, '2025-07-02', 12),
            (3, 3, '2025-07-01', 15), (3, 3, '2025-07-02', 18),
            (4, 3, '2025-07-01', 5), (4, 3, '2025-07-02', 7),
            (5, 3, '2025-07-01', 10), (5, 3, '2025-07-02', 12),
            # Kochi
            (1, 4, '2025-07-01', 15), (1, 4, '2025-07-02', 20),
            (2, 4, '2025-07-01', 8), (2, 4, '2025-07-02', 10),
            (3, 4, '2025-07-01', 12), (3, 4, '2025-07-02', 15),
            (4, 4, '2025-07-01', 6), (4, 4, '2025-07-02', 8),
            (5, 4, '2025-07-01', 10), (5, 4, '2025-07-02', 12),
            # Coimbatore
            (1, 5, '2025-07-01', 12), (1, 5, '2025-07-02', 18),
            (2, 5, '2025-07-01', 7), (2, 5, '2025-07-02', 9),
            (3, 5, '2025-07-01', 10), (3, 5, '2025-07-02', 13),
            (4, 5, '2025-07-01', 5), (4, 5, '2025-07-02', 7),
            (5, 5, '2025-07-01', 8), (5, 5, '2025-07-02', 10),
            # Delhi
            (1, 6, '2025-07-01', 18), (1, 6, '2025-07-02', 22),
            (2, 6, '2025-07-01', 10), (2, 6, '2025-07-02', 12),
            (3, 6, '2025-07-01', 15), (3, 6, '2025-07-02', 18),
            (4, 6, '2025-07-01', 8), (4, 6, '2025-07-02', 10),
            (5, 6, '2025-07-01', 12), (5, 6, '2025-07-02', 15),
            # Mumbai
            (1, 7, '2025-07-01', 20), (1, 7, '2025-07-02', 25),
            (2, 7, '2025-07-01', 12), (2, 7, '2025-07-02', 15),
            (3, 7, '2025-07-01', 10), (3, 7, '2025-07-02', 12),
            (4, 7, '2025-07-01', 15), (4, 7, '2025-07-02', 18),
            (5, 7, '2025-07-01', 10), (5, 7, '2025-07-02', 12)
        ]
        cur.executemany(
            "INSERT INTO sales (sku_id, store_id, sale_date, quantity) VALUES (%s, %s, %s, %s)",
            sales
        )

        # Seed InventoryItem
        inventory_items = [
            (1, 'Rice 5kg', 500, 1), (2, 'Oil 1L', 200, 1), (3, 'Dal 1kg', 800, 1), (4, 'Soap', 600, 1), (5, 'Shampoo 200ml', 700, 1),  # Bengaluru DC
            (6, 'Rice 5kg', 300, 2), (7, 'Dal 1kg', 150, 2), (8, 'Soap', 200, 2), (9, 'Shampoo 200ml', 250, 2),  # Delhi DC
            (10, 'Rice 5kg', 400, 3), (11, 'Oil 1L', 250, 3), (12, 'Dal 1kg', 300, 3), (13, 'Soap', 500, 3)  # Mumbai DC
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
