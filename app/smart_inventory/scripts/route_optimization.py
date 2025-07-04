#!/usr/bin/env python
"""
route_optimization.py
Purpose: Optimizes last-mile delivery routes for Walmart's SmartRetailSync project using OR-Tools, prioritizing urgent
deliveries based on reorder alerts.

Execution: Run after demand_forecasting.py.
Command: python scripts/route_optimization.py
"""
import pandas as pd
from sqlalchemy import create_engine
import psycopg2
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
import logging
import numpy as np
from datetime import datetime

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

def create_distance_matrix():
    try:
        query = """
            SELECT DISTINCT origin, destination, distance_km
            FROM logistics
            WHERE origin = 'Atlanta';
        """
        df = pd.read_sql(query, engine)
        destinations = sorted(list(set(df['destination'].unique()) - {'Atlanta'}))
        locations = ['Atlanta'] + destinationsEnhancements with Real-World Explanations
        n = len(locations)
        distance_matrix = np.zeros((n, n))
        for _, row in df.iterrows():
            i = locations.index(row['origin'])
            j = locations.index(row['destination'])
            distance_matrix[i][j] = row['distance_km']
            distance_matrix[j][i] = row['distance_km']
        logging.debug(f"Distance matrix shape: {distance_matrix.shape}")
        logging.debug(f"Locations: {locations}")
        return distance_matrix, locations
    except Exception as e:
        logging.error(f"Error creating distance matrix: {e}")
        return None, None

def get_delivery_demands():
    try:
        query = """
            SELECT r.sku_id, r.store_location, (r.reorder_threshold - r.current_stock)::integer AS demand
            FROM reorder_alerts r
            WHERE r.reorder_threshold > r.current_stock;
        """
        df = pd.read_sql(query, engine)
        if df.empty:
            logging.warning("No demands from reorder_alerts")
            return {}
        logging.debug(f"Demands DataFrame (raw): {df.to_dict()}")
        df['demand'] = df['demand'].clip(lower=0).round().astype(int)
        demands = df.groupby('store_location')['demand'].sum().to_dict()
        logging.debug(f"Aggregated demands: {demands}")
        logging.debug(f"Total demand: {sum(demands.values())}")
        if 'Atlanta' in demands:
            logging.warning(f"Removing depot demand for Atlanta: {demands['Atlanta']}")
            del demands['Atlanta']
        return demands
    except Exception as e:
        logging.error(f"Error getting delivery demands: {e}")
        return {}

def optimize_routes():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE delivery_routes RESTART IDENTITY;")
        cur.execute("TRUNCATE TABLE logistics_metrics RESTART IDENTITY;")
        conn.commit()
        distance_matrix, locations = create_distance_matrix()
        if distance_matrix is None:
            logging.error("Failed to create distance matrix")
            return
        demands = get_delivery_demands()
        if not demands:
            logging.warning("No delivery demands found")
            return
        reorder_locations = set(demands.keys())
        logistics_locations = set(locations[1:])
        missing_locations = reorder_locations - logistics_locations
        if missing_locations:
            logging.warning(f"Locations in reorder_alerts but not in logistics: {missing_locations}")
        demand_vector = [0] * len(locations)
        for loc in locations[1:]:
            demand_vector[locations.index(loc)] = int(demands.get(loc, 0))
        logging.debug(f"Demand vector: {demand_vector}")
        data = {
            'distance_matrix': distance_matrix,
            'demands': demand_vector,
            'vehicle_capacities': [5000] * 3,
            'num_vehicles': 3,
            'depot': 0
        }
        manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']), data['num_vehicles'], data['depot'])
        routing = pywrapcp.RoutingModel(manager)
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(data['distance_matrix'][from_node][to_node] * 1000)
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return data['demands'][from_node]
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity'
        )
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
        search_parameters.time_limit.seconds = 60
        solution = routing.SolveWithParameters(search_parameters)
        if solution:
            routes = []
            total_distance = 0
            for vehicle_id in range(data['num_vehicles']):
                index = routing.Start(vehicle_id)
                sequence = 0
                route_distance = 0
                route = []
                while not routing.IsEnd(index):
                    node = manager.IndexToNode(index)
                    route.append(locations[node])
                    if node != 0:
                        store = locations[node]
                        sku_query = f"""
                            SELECT sku_id FROM reorder_alerts WHERE store_location = '{store}'
                            LIMIT 1;
                        """
                        sku_df = pd.read_sql(sku_query, engine)
                        sku_id = int(sku_df['sku_id'].iloc[0]) if not sku_df.empty else 1
                        next_index = solution.Value(routing.NextVar(index))
                        distance = float(data['distance_matrix'][node][manager.IndexToNode(next_index)])
                        if sequence == 0:
                            prev_distance = float(data['distance_matrix'][0][node])
                        else:
                            prev_node = manager.IndexToNode(previous_index)
                            prev_distance = float(data['distance_matrix'][prev_node][node])
                        estimated_time = int(max(1, (prev_distance / 60) + 0.25))  # 60 km/h + 15 min stop
                        routes.append((vehicle_id, sku_id, store, sequence, prev_distance, estimated_time))
                    previous_index = index
                    index = solution.Value(routing.NextVar(index))
                    sequence += 1
                    route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id) / 1000
                total_distance += route_distance
                logging.info(f"Vehicle {vehicle_id} route: {' -> '.join(route)}")
                logging.info(f"Vehicle {vehicle_id} route distance: {route_distance:.2f} km")
            if routes:
                cur.executemany(
                    """
                    INSERT INTO delivery_routes (vehicle_id, sku_id, store_location, sequence, distance_km, estimated_time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [(int(r[0]), int(r[1]), r[2], int(r[3]), float(r[4]), int(r[5])) for r in routes]
                )
                fuel_cost_per_km = 0.1
                co2_per_km = 0.2
                total_cost = total_distance * fuel_cost_per_km
                total_co2 = total_distance * co2_per_km
                cur.execute(
                    """
                    INSERT INTO logistics_metrics (run_date, total_distance_km, total_fuel_cost, total_co2_kg)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (datetime.now().date(), float(total_distance), float(total_cost), float(total_co2))
                )
                conn.commit()
                logging.info(f"Saved {len(routes)} route entries. Total distance: {total_distance:.2f} km, Cost: ${total_cost:.2f}, CO2: {total_co2:.2f} kg")
            else:
                logging.warning("No routes generated")
        else:
            logging.warning("No VRP solution found")
    except Exception as e:
        logging.error(f"Error optimizing routes: {e}")
        conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    optimize_routes()
