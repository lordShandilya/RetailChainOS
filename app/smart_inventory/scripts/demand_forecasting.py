"""
demand_forecasting.py
Purpose: Generates demand forecasts for SKUs based on sales data and creates reorder alerts for SmartInventory.
Execution: Run after seed_data.py.
Command: python app/smart_inventory/demand_forecasting.py
"""
import pandas as pd
from sqlalchemy import create_engine
import psycopg2
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

DB_PARAMS = {
    "dbname": "walmart_db",
    "user": "walmart_user",
    "password": "securepassword",
    "host": "localhost",
    "port": "5432"
}

SQLALCHEMY_URI = f"postgresql+psycopg2://{DB_PARAMS['user']}:{DB_PARAMS['password']}@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['dbname']}"
engine = create_engine(SQLALCHEMY_URI)

def get_sales_data(sku_id, store_id):
    try:
        query = """
            SELECT sale_date AS ds, quantity AS y
            FROM sales
            WHERE sku_id = %s AND store_id = %s
            ORDER BY sale_date;
        """
        df = pd.read_sql(query, engine, params=(sku_id, store_id))
        if df.empty:
            logging.warning(f"No sales data for SKU {sku_id}, store {store_id}")
            return pd.DataFrame()
        df['y'] = df['y'].clip(upper=100)
        logging.debug(f"Sales data for SKU {sku_id}, store {store_id}: {len(df)} rows")
        return df
    except Exception as e:
        logging.error(f"Error fetching sales data for SKU {sku_id}, store {store_id}: {e}")
        return pd.DataFrame()

def forecast_sku(sku_id, store_id, conn, cur):
    logging.info(f"Forecasting SKU {sku_id} for store {store_id}")
    try:
        sales_df = get_sales_data(sku_id, store_id)
        if sales_df.empty:
            return
        avg_daily_sales = sales_df['y'].mean()
        monthly_demand = min(round(avg_daily_sales * 30), 100)  # Cap at 100 units
        cur.execute(
            """
            INSERT INTO forecasts (store_id, sku_id, predicted_demand)
            VALUES (%s, %s, %s)
            ON CONFLICT (store_id, sku_id) DO UPDATE
            SET predicted_demand = EXCLUDED.predicted_demand
            """,
            (store_id, sku_id, monthly_demand)
        )
        logging.info(f"Saved forecast for SKU {sku_id}, store {store_id}: {monthly_demand}")
    except Exception as e:
        logging.error(f"Error forecasting SKU {sku_id}, store {store_id}: {e}")

def generate_reorder_alerts(conn, cur):
    try:
        query = """
            SELECT f.store_id, f.sku_id, f.predicted_demand, i.current_stock
            FROM forecasts f
            JOIN inventory i ON f.store_id = i.store_id AND f.sku_id = i.sku_id
            WHERE i.store_id IS NOT NULL
        """
        df = pd.read_sql(query, engine)
        if df.empty:
            logging.warning("No forecast data for reorder alerts")
            return
        safety_stock = 20
        df['reorder_threshold'] = df['predicted_demand'] + safety_stock
        df['priority_score'] = (df['reorder_threshold'] - df['current_stock']) / df['reorder_threshold'].clip(lower=1)
        df['priority_score'] = df['priority_score'].clip(0, 1)
        alerts = df[df['current_stock'] < df['reorder_threshold']][[
            'store_id', 'sku_id', 'current_stock', 'reorder_threshold', 'priority_score'
        ]]
        alert_data = [
            (int(row['store_id']), int(row['sku_id']), int(row['current_stock']),
             int(row['reorder_threshold']), float(row['priority_score']))
            for _, row in alerts.iterrows()
        ]
        cur.execute("TRUNCATE TABLE reorder_alerts RESTART IDENTITY;")
        cur.executemany(
            """
            INSERT INTO reorder_alerts (store_id, sku_id, current_stock, reorder_threshold, priority_score)
            VALUES (%s, %s, %s, %s, %s)
            """,
            alert_data
        )
        logging.info(f"Saved {len(alert_data)} reorder alerts")
    except Exception as e:
        logging.error(f"Error generating reorder alerts: {e}")

def run_forecasting():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE forecasts RESTART IDENTITY;")
        conn.commit()
        sku_ids = [1, 2, 3, 4, 5]
        store_ids = [1, 2, 3, 4, 5, 6, 7]  # Updated to 7 stores
        for store_id in store_ids:
            for sku_id in sku_ids:
                forecast_sku(sku_id, store_id, conn, cur)
        conn.commit()
        generate_reorder_alerts(conn, cur)
        conn.commit()
        print("Demand forecasting and reorder alerts completed successfully")
    except Exception as e:
        logging.error(f"Error during forecasting: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    run_forecasting()
