import logging
import pandas as pd
import psycopg2
from fastapi import FastAPI, WebSocket
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from sqlalchemy import create_engine
import redis
import json
from datetime import datetime, timedelta
import mapbox
from mapbox import Directions
import asyncio

# Configure logging
logging.basicConfig(filename='routeai_trackx.log', level=logging.INFO)

# Database and Redis setupDB_PARAMS = {
    "dbname": "retailchain_os",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}
engine = create_engine(f"postgresql://{DB_PARAMS['user']}:{DB_PARAMS['password']}@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['dbname']}")
redis_client = redis.Redis(host='localhost', port=6379, db=0)
app = FastAPI()
MAPBOX_ACCESS_TOKEN = "your_mapbox_access_token"

# Initialize Mapbox Directions API
directions_client = Directions(access_token=MAPBOX_ACCESS_TOKEN)

def create_distance_matrix():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    query = """
        SELECT origin, destination, distance_km
        FROM logistics
        WHERE origin = 'Atlanta' OR destination = 'Atlanta';
    """
    df = pd.read_sql(query, engine)
    locations = sorted(set(df['origin']).union(set(df['destination'])))
    if 'Atlanta' in locations:
        locations.remove('Atlanta')
        locations.insert(0, 'Atlanta')
    n = len(locations)
    distance_matrix = [[0] * n for _ in range(n)]
    for _, row in df.iterrows():
        i = locations.index(row['origin'])
        j = locations.index(row['destination'])
        distance_matrix[i][j] = float(row['distance_km'])
        distance_matrix[j][i] = float(row['distance_km'])
    conn.close()
    return distance_matrix, locations

def get_delivery_demands():
    query = """
        SELECT r.sku_id, r.store_location, (r.reorder_threshold - r.current_stock)::integer AS demand,
               (r.reorder_threshold - r.current_stock)::float / GREATEST(r.current_stock, 1) AS priority_score
        FROM reorder_alerts r
        WHERE r.reorder_threshold > r.current_stock;
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        logging.warning("No demands from reorder_alerts")
        return {}, {}
    logging.debug(f"Demands DataFrame: {df[['sku_id', 'store_location', 'demand', 'priority_score']].to_dict()}")
    df['demand'] = df['demand'].clip(lower=0).round().astype(int)
    demands = df.groupby('store_location')['demand'].sum().to_dict()
    priorities = df.groupby('store_location')['priority_score'].mean().to_dict()
    if 'Atlanta' in demands:
        del demands['Atlanta']
        del priorities['Atlanta']
    return demands, priorities

async def update_vehicle_location(vehicle_id, latitude, longitude, route):
    redis_client.set(f"vehicle_{vehicle_id}", json.dumps({"lat": latitude, "lng": longitude}))
    planned_route = json.loads(redis_client.get(f"route_{vehicle_id}") or "[]")
    if planned_route:
        current_pos = {"lat": latitude, "lng": longitude}
        next_stop = planned_route[0]
        response = directions_client.directions([current_pos, next_stop], profile="driving")
        if response.status_code == 200:
            distance = response.json()['routes'][0]['distance'] / 1000  # km
            if distance > 1:
                logging.warning(f"Vehicle {vehicle_id} deviated >1km from route")
                # Notify logistics manager (future enhancement)
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tracking_logs (vehicle_id, latitude, longitude, timestamp)
        VALUES (%s, %s, %s, %s)
        """,
        (vehicle_id, latitude, longitude, datetime.now())
    )
    conn.commit()
    conn.close()

@app.websocket("/ws/track/{vehicle_id}")
async def websocket_endpoint(websocket: WebSocket, vehicle_id: int):
    await websocket.accept()
    try:
        while True:
            location_data = redis_client.get(f"vehicle_{vehicle_id}")
            if location_data:
                await websocket.send_json(json.loads(location_data))
            await asyncio.sleep(5)  # Update every 5 seconds
    except Exception as e:
        logging.error(f"WebSocket error for vehicle {vehicle_id}: {e}")
    finally:
        await websocket.close()

def optimize_routes():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE delivery_routes RESTART IDENTITY;")
    cur.execute("TRUNCATE TABLE logistics_metrics RESTART IDENTITY;")
    cur.execute("TRUNCATE TABLE tracking_logs RESTART IDENTITY;")
    conn.commit()
    distance_matrix, locations = create_distance_matrix()
    demands, priorities = get_delivery_demands()
    demand_vector = [0] * len(locations)
    priority_vector = [0] * len(locations)
    for loc in locations[1:]:
        idx = locations.index(loc)
        demand_vector[idx] = int(demands.get(loc, 0))
        priority_vector[idx] = float(priorities.get(loc, 0))
    data = {
        'distance_matrix': distance_matrix,
        'demands': demand_vector,
        'vehicle_capacities': [5000] * 3,
        'num_vehicles': 3,
        'depot': 0,
        'priorities': priority_vector
    }
    manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']), data['num_vehicles'], data['depot'])
    routing = pywrapcp.RoutingModel(manager)
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        priority_weight = 1000 * data['priorities'][to_node] if to_node != 0 else 0
        return int(data['distance_matrix'][from_node][to_node] * 1000 + priority_weight)
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity')
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        routes = []
        total_distance = 0
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            sequence = 0
            route_distance = 0
            route_coords = [{"lat": 33.7490, "lng": -84.3880}]  # Atlanta
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node != 0:
                    store = locations[node]
                    sku_query = f"SELECT sku_id, priority_score FROM reorder_alerts WHERE store_location = '{store}' LIMIT 1;"
                    sku_df = pd.read_sql(sku_query, engine)
                    sku_id = int(sku_df['sku_id'].iloc[0]) if not sku_df.empty else 1
                    priority_score = float(sku_df['priority_score'].iloc[0]) if not sku_df.empty else 0
                    prev_distance = float(data['distance_matrix'][0 if sequence == 0 else manager.IndexToNode(previous_index)][node])
                    estimated_time = max(1, prev_distance / 60 + 0.25)
                    routes.append((vehicle_id, sku_id, store, sequence, prev_distance, estimated_time, priority_score))
                    route_coords.append({"lat": 29.7604, "lng": -95.3698} if store == 'Houston' else {"lat": 41.8781, "lng": -87.6298} if store == 'Chicago' else {"lat": 32.7767, "lng": -96.7970})
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                sequence += 1
                route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id) / 1000
            total_distance += route_distance
            redis_client.set(f"route_{vehicle_id}", json.dumps(route_coords))
        cur.executemany(
            """
            INSERT INTO delivery_routes (vehicle_id, sku_id, store_location, sequence, distance_km, estimated_time, priority_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [(int(r[0]), int(r[1]), r[2], int(r[3]), float(r[4]), float(r[5]), float(r[6])) for r in routes]
        )
        cur.execute(
            """
            INSERT INTO logistics_metrics (run_date, total_distance_km, total_fuel_cost, total_co2_kg)
            VALUES (%s, %s, %s, %s)
            """,
            (datetime.now().date(), float(total_distance), float(total_distance * 0.1), float(total_distance * 0.2))
        )
        conn.commit()
    conn.close()

if __name__ == "__main__":
    optimize_routes()
