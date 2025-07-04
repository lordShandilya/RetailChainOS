from typing import List, Dict, Any, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from db import get_session
from services import get_fulfillment_centers, find_fulfillment_center

app = FastAPI()

class Order(BaseModel):
    latitude: float
    longitude: float
    sku: str
    quantity: int

@app.get("/fulfillment/assign")
def assign_fulfillment_center(order: Order):
    session = get_session()
    if not session:
        raise HTTPException(status_code=500, detail="Database connection error")

    fc_map = get_fulfillment_centers(session)
    closest_fc, min_score = find_fulfillment_center(
        lat=order.latitude,
        lon=order.longitude,
        sku=order.sku,
        quantity=order.quantity,
        fc_map=fc_map
    )

    if not closest_fc:
        raise HTTPException(status_code=404, detail="No suitable fulfillment center found")

    return {"fulfillment_center_id": closest_fc, "score": min_score}