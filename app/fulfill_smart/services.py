from db import get_session
from models import FulfillmentCenter, InventoryItem
import math



def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def find_dist(fc_lat, fc_lon, lat, lon):
    return haversine_distance(fc_lat, fc_lon, lat, lon)

def get_fulfillment_centers(session):
    fulfillment_centers = session.query(FulfillmentCenter).all()
    fc_map = {}
    
    for fc in fulfillment_centers:
        inventory_items = {item.sku: item.quantity for item in fc.inventory_items}
        fc_map[fc.id] = {
            "latitude": fc.latitude,
            "longitude": fc.longitude,
            "current_workload": fc.current_workload,
            "handling_capacity": fc.handling_capacity,
            "inventory_items": inventory_items
        }
    
    return fc_map

def calculate_delivery_cost(base_fee, cost_per_km, distance, weight_fee, order_weight, urgency_fee):
    return base_fee + (cost_per_km * distance) + (weight_fee * order_weight) + urgency_fee

def find_fulfillment_center(lat, lon, sku, quantity, fc_map):
    closest_fc = None
    min_score = float('inf')

    for fc_id, fc_data in fc_map.items():
        if sku in fc_data["inventory_items"] and fc_data["inventory_items"][sku] >= quantity:
            distance = find_dist(fc_data["latitude"], fc_data["longitude"], lat, lon)
            cost = calculate_delivery_cost(
                base_fee=50,  # Example base fee
                cost_per_km=10,  # Example cost per km
                distance=distance,
                weight_fee=5,  # Example weight fee per kg
                order_weight=quantity * 0.5,  # Assuming each item weighs 0.5 kg
                urgency_fee=20  # Example urgency fee
            )
            score = (distance * 0.5) + (fc_data["current_workload"]/fc_data["handling_capacity"] * 0.3) + (cost * 0.2)
            if score < min_score:
                min_score = score
                closest_fc = fc_id
    
    
    return closest_fc, min_score if closest_fc else None


