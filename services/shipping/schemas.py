from pydantic import BaseModel
from typing import Optional


class ShipmentAddress(BaseModel):
    name: str
    address: str
    city: str


class ShipmentCreate(BaseModel):
    orderId: str
    address: ShipmentAddress


class ShipmentStatusUpdate(BaseModel):
    status: str


class ShipmentResponse(BaseModel):
    id: str
    orderId: str
    address: ShipmentAddress
    trackingNumber: str
    status: str
    createdAt: str
    updatedAt: str

