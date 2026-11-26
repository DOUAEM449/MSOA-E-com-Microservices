from datetime import timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, StringConstraints, UUID4, field_validator


class ShipmentAddress(BaseModel):
    name: str
    address: str
    city: str


class ShipmentCreate(BaseModel):
    orderId: str
    address: ShipmentAddress


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RequestedAddress(ShipmentAddress):
    name: NonBlank
    address: NonBlank
    city: NonBlank


class ShipmentRequested(BaseModel):
    messageId: UUID4
    type: Literal["ShipmentRequested"]
    orderId: NonBlank
    paymentId: NonBlank
    address: RequestedAddress
    occurredAt: AwareDatetime

    @field_validator("occurredAt", mode="before")
    @classmethod
    def timestamp_string(cls, value):
        if not isinstance(value, str) or "T" not in value:
            raise ValueError("Expected an ISO-8601 timestamp")
        return value

    @field_validator("occurredAt")
    @classmethod
    def utc_timestamp(cls, value):
        if value.utcoffset() != timedelta(0):
            raise ValueError("Expected a UTC timestamp")
        return value


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

