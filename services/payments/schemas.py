from pydantic import BaseModel
from typing import Optional


class PaymentCreate(BaseModel):
    orderId: str
    method: str


class PaymentResponse(BaseModel):
    id: str
    orderId: str
    amount: float
    method: str
    status: str
    createdAt: str

