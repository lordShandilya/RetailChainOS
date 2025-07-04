from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

Base = declarative_base()

class FulfillmentCenter(Base):
    __tablename__ = 'FulfillmentCenter'

    id = Column(Integer, primary_key = True, autoincrement=True)
    latitude = Column(Float)
    longitude = Column(Float)
    current_workload = Column(Integer)
    handling_capacity = Column(Integer)

    inventory_items = relationship("InventoryItem", back_populates="fulfillment_center", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FulfillmentCenters(id={self.id}, location=[longitude: {self.longitude}, latitude: {self.latitude}], current_workload={self.current_workload}, handling_capacity={self.handling_capacity})>"
    
class InventoryItem(Base):
    __tablename__ = 'InventoryItem'

    id = Column(Integer, primary_key = True, autoincrement=True)
    sku = Column(String)
    quantity = Column(Integer)
    fulfillment_center_id = Column(Integer, ForeignKey('FulfillmentCenter.id'))

    fulfillment_center = relationship("FulfillmentCenter", back_populates="inventory_items")

    def __repr__(self):
        return f"<InventoryItem(id={self.id}, sku={self.sku}, quantity={self.quantity}, fulfillment_center_id={self.fulfillment_center_id})>"