from app.fulfill_smart.utils.db import get_session
from models.models import FulfillmentCenter, InventoryItem

session = get_session()

fulfillment_centers = [
    FulfillmentCenter(
        id="FC001",
        latitude=12.9716,
        longitude=77.5946,
        current_workload=120,
        handling_capacity=500,
        inventory_items=[
            InventoryItem(sku="SKU001", quantity=500),
            InventoryItem(sku="SKU002", quantity=200)
        ]
    ),
    FulfillmentCenter(
        id="FC002",
        latitude=28.7041,
        longitude=77.1025,
        current_workload=80,
        handling_capacity=400,
        inventory_items=[
            InventoryItem(sku="SKU001", quantity=300),
            InventoryItem(sku="SKU003", quantity=150)
        ]
    ),
    FulfillmentCenter(
        id="FC003",
        latitude=19.0760,
        longitude=72.8777,
        current_workload=200,
        handling_capacity=600,
        inventory_items=[
            InventoryItem(sku="SKU002", quantity=250),
            InventoryItem(sku="SKU004", quantity=500)
        ]
    )
]

def populate_fulfillment_centers():
    session.add_all(fulfillment_centers)
    session.commit()
    print("Fulfillment centers populated successfully.")

if __name__ == "__main__":
    populate_fulfillment_centers()
