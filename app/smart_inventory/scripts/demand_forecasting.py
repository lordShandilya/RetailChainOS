#!/usr/bin/env python
"""
demand_forecasting.py
Purpose: Generates demand forecasts for each SKU using Facebook's Prophet model and creates reorder alerts for low stock
levels in the SmartRetailSync project. This script leverages historical sales and external factors (e.g., holidays, weather)
to predict future demand, aligning with Walmart's goal of optimizing inventory management and preventing stockouts/overstock.

Why use this script:
- Uses Prophet for accurate time-series forecasting with seasonality and external regressors, ideal for retail data.
- Incorporates Walmart-specific data (e.g., holiday sales spikes) for realistic predictions.
- Generates actionable reorder alerts, making forecasts directly usable for inventory decisions.
- Evaluates model performance to demonstrate reliability to hackathon judges.
- Uses SQLAlchemy for robust database queries, aligning with enterprise standards.
- Handles multiple SKUs for scalability, mimicking Walmart's massive inventory.

Execution: Run this script after seed_data.py to generate forecasts and alerts.
Command: python scripts/demand_forecasting.py
Prerequisites: Install dependencies (pandas, sqlalchemy, psycopg2-binary, prophet, scikit-learn).
"""

import pandas as pd
from sqlalchemy import create_engine
import psycopg2
from prophet import Prophet
from sklearn.metrics import mean_absolute_error
import logging
import warnings

# Suppress pandas SQLAlchemy warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database connection parameters
DB_PARAMS = {
    "dbname": "walmart_db",
    "user": "walmart_user",
    "password": "securepassword",
    "host": "localhost",
    "port": "5432"
}

# Create SQLAlchemy engine
SQLALCHEMY_URI = f"postgresql+psycopg2://{DB_PARAMS['user']}:{DB_PARAMS['password']}@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['dbname']}"
engine = create_engine(SQLALCHEMY_URI)

# Weather impact mapping
WEATHER_MAP = {'Sunny': 1.0, 'Cloudy': 0.8, 'Rainy': 0.5, 'Snowy': 0.3}

def get_sales_data(sku_id):
    """
    Fetches sales data for a specific SKU, formatted for Prophet.
    Why: Ensures clean, continuous time-series data with filled gaps for accurate forecasting.
    """
    try:
        query = f"""
            SELECT sale_date AS ds, quantity AS y
            FROM sales
            WHERE sku_id = {sku_id}
            ORDER BY sale_date;
        """
        df = pd.read_sql(query, engine)
        if df.empty:
            logging.warning(f"No sales data for SKU {sku_id}")
            return df
        # Ensure continuous weekly data
        date_range = pd.date_range(start=df['ds'].min(), end=df['ds'].max(), freq='7D')
        df = df.set_index('ds').reindex(date_range, fill_value=0).reset_index()
        df.rename(columns={'index': 'ds'}, inplace=True)
        df['y'] = df['y'].clip(upper=100)  # Cap outliers for robustness
        logging.debug(f"Sales data for SKU {sku_id}: {len(df)} rows")
        return df
    except Exception as e:
        logging.error(f"Error fetching sales data for SKU {sku_id}: {e}")
        return pd.DataFrame()

def get_external_factors(store_location):
    """
    Fetches external factors (holidays, weather) for a store location.
    Why: Enhances forecast accuracy by accounting for real-world influences like holidays and weather.
    """
    try:
        query = f"""
            SELECT factor_date AS ds, holiday, weather
            FROM external_factors
            WHERE store_location = '{store_location}';
        """
        df = pd.read_sql(query, engine)
        df['ds'] = pd.to_datetime(df['ds'])  # Ensure datetime
        logging.debug(f"External factors for {store_location}: {len(df)} rows")
        return df
    except Exception as e:
        logging.error(f"Error fetching external factors for {store_location}: {e}")
        return pd.DataFrame()

def forecast_sku(sku_id, conn, cur):
    """
    Generates 30-day demand forecast for a single SKU and saves to database.
    Why: Modular function enables scalable forecasting across multiple SKUs, critical for Walmart's inventory scale.
    """
    logging.info(f"Forecasting SKU {sku_id}")
    try:
        # Get sales data
        sales_df = get_sales_data(sku_id)
        if sales_df.empty:
            return

        # Get store location
        store_location = pd.read_sql(f"SELECT store_location FROM products WHERE sku_id = {sku_id};", engine)['store_location'].iloc[0]

        # Prepare holidays and weather
        external_df = get_external_factors(store_location)
        holidays = None
        weather_df = pd.DataFrame()
        if not external_df.empty:
            # Create holidays DataFrame with required columns
            holiday_rows = external_df[external_df['holiday'] == True][['ds']].drop_duplicates()
            if not holiday_rows.empty:
                holiday_rows['holiday'] = 'Holiday'  # Assign generic name
                holidays = holiday_rows[['ds', 'holiday']]
                logging.debug(f"Holidays for SKU {sku_id}: {len(holidays)} rows")
            weather_df = external_df.copy()
            weather_df['weather_effect'] = weather_df['weather'].map(WEATHER_MAP)

        # Merge weather data
        if not weather_df.empty:
            try:
                sales_df = sales_df.merge(weather_df[['ds', 'weather_effect']], on='ds', how='left')
                sales_df['weather_effect'] = sales_df['weather_effect'].fillna(1.0)
            except Exception as e:
                logging.error(f"Error merging weather data for SKU {sku_id}: {e}")
                return

        # Train Prophet model
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False  # Weekly data
        )
        if holidays is not None:
            model.holidays = holidays
        if not weather_df.empty:
            model.add_regressor('weather_effect')
        model.fit(sales_df)

        # Generate future dates
        future = model.make_future_dataframe(periods=30, freq='D')
        if not weather_df.empty:
            future['weather_effect'] = 1.0  # Placeholder for future weather
        forecast = model.predict(future)
        forecast = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(30)
        forecast['sku_id'] = sku_id

        # Save forecasts to database
        forecast_data = [
            (row['sku_id'], row['ds'].date(), round(row['yhat'], 2), round(row['yhat_lower'], 2), round(row['yhat_upper'], 2))
            for _, row in forecast.iterrows()
        ]
        cur.executemany(
            """
            INSERT INTO forecasts (sku_id, forecast_date, predicted_quantity, lower_bound, upper_bound)
            VALUES (%s, %s, %s, %s, %s)
            """,
            forecast_data
        )
        logging.info(f"Saved {len(forecast_data)} forecasts for SKU {sku_id}")
    except Exception as e:
        logging.error(f"Error forecasting SKU {sku_id}: {e}")

def generate_reorder_alerts(conn, cur):
    """
    Creates reorder alerts for SKUs with low stock based on forecasts.
    Why: Translates predictions into actionable inventory decisions, aligning with Walmart's efficiency goals.
    """
    try:
        query = """
            SELECT f.sku_id, f.forecast_date, f.predicted_quantity, i.store_location, i.stock_level
            FROM forecasts f
            JOIN inventory i ON f.sku_id = i.sku_id
            WHERE f.forecast_date >= CURRENT_DATE;
        """
        df = pd.read_sql(query, engine)
        if df.empty:
            logging.warning("No forecast data for reorder alerts")
            return
        safety_stock = 20
        df['reorder_threshold'] = df.groupby('sku_id')['predicted_quantity'].transform(lambda x: x.rolling(7, min_periods=1).sum()) + safety_stock
        alerts = df[df['stock_level'] < df['reorder_threshold']][['sku_id', 'store_location', 'reorder_threshold', 'stock_level', 'forecast_date']]

        alert_data = [
            (row['sku_id'], row['store_location'], row['reorder_threshold'], row['stock_level'], row['forecast_date'])
            for _, row in alerts.iterrows()
        ]
        cur.executemany(
            """
            INSERT INTO reorder_alerts (sku_id, store_location, reorder_threshold, current_stock, alert_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            alert_data
        )
        logging.info(f"Saved {len(alert_data)} reorder alerts")
    except Exception as e:
        logging.error(f"Error generating reorder alerts: {e}")

def evaluate_model(sku_id):
    """
    Evaluates Prophet model performance for a single SKU using MAE.
    Why: Demonstrates forecast reliability to judges, enhancing project credibility.
    """
    try:
        sales_df = get_sales_data(sku_id)
        if sales_df.empty:
            logging.warning(f"Cannot evaluate SKU {sku_id}: no sales data")
            return None
        train_size = int(0.8 * len(sales_df))
        train_df = sales_df[:train_size]
        test_df = sales_df[train_size:]
        model = Prophet(yearly_seasonality=True)
        model.fit(train_df)
        future = model.make_future_dataframe(periods=len(test_df), freq='7D')
        forecast = model.predict(future)
        test_forecast = forecast.tail(len(test_df))[['ds', 'yhat']]
        test_df = test_df.merge(test_forecast, on='ds')
        mae = mean_absolute_error(test_df['y'], test_df['yhat'])
        logging.info(f"Mean Absolute Error for SKU {sku_id}: {mae:.2f}")
        return mae
    except Exception as e:
        logging.error(f"Error evaluating SKU {sku_id}: {e}")
        return None

def run_forecasting():
    """Main function to orchestrate demand forecasting and reorder alerts."""
    try:
        # Use psycopg2 for cursor operations (inserts)
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Clear existing forecasts and alerts
        logging.info("Clearing existing forecasts and alerts")
        cur.execute("TRUNCATE TABLE forecasts, reorder_alerts RESTART IDENTITY;")
        conn.commit()

        # Forecast for all SKUs (limit to 10 for testing, adjust for full run)
        sku_ids = pd.read_sql("SELECT DISTINCT sku_id FROM products LIMIT 10;", engine)['sku_id'].tolist()
        for sku_id in sku_ids:
            forecast_sku(sku_id, conn, cur)
        conn.commit()

        # Generate reorder alerts
        logging.info("Generating reorder alerts")
        generate_reorder_alerts(conn, cur)
        conn.commit()

        # Evaluate model for SKU 1
        logging.info("Evaluating model for SKU 1")
        evaluate_model(1)

        print("Demand forecasting and reorder alerts completed successfully")

    except Exception as e:
        logging.error(f"Error during forecasting: {e}")
        conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    run_forecasting()
