from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class RequestModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class CustomerInput(RequestModel):
    name: str = Field(min_length=1, max_length=160)
    address: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=160)
    email: Optional[str] = Field(default=None, max_length=320)

    @field_validator("name", "address", "city")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class OrderItemInput(RequestModel):
    product_id: int = Field(alias="productId", gt=0, strict=True)
    quantity: int = Field(ge=1, le=10000, strict=True)


class CreateOrderInput(RequestModel):
    user_id: str = Field(alias="userId", min_length=1, max_length=200)
    customer: CustomerInput
    items: List[OrderItemInput] = Field(min_length=1, max_length=100)

    @field_validator("user_id")
    @classmethod
    def strip_user_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class UpdateStatusInput(RequestModel):
    status: OrderStatus
