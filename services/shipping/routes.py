from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from schemas import ShipmentCreate, ShipmentStatusUpdate
import shipping_service

router = APIRouter(prefix="/api/shipments")


@router.get("")
def list_shipments():
    """GET /api/shipments — list all shipments."""
    return shipping_service.list_shipments()


@router.get("/order/{order_id}")
def get_shipment_by_order(order_id: str):
    """GET /api/shipments/order/{orderId} — shipment for a specific order."""
    shipment = shipping_service.get_shipment_by_order(order_id)
    if not shipment:
        return JSONResponse(status_code=404, content={"message": f"No shipment found for order {order_id}"})
    return shipment


@router.post("", status_code=201)
async def create_shipment(body: ShipmentCreate):
    """POST /api/shipments — create a shipment."""
    if not body.orderId or not body.orderId.strip():
        return JSONResponse(status_code=400, content={"message": "orderId is required"})
    if not body.address.name or not body.address.name.strip():
        return JSONResponse(status_code=400, content={"message": "address.name is required"})
    if not body.address.address or not body.address.address.strip():
        return JSONResponse(status_code=400, content={"message": "address.address is required"})
    if not body.address.city or not body.address.city.strip():
        return JSONResponse(status_code=400, content={"message": "address.city is required"})

    address_dict = {
        "name": body.address.name.strip(),
        "address": body.address.address.strip(),
        "city": body.address.city.strip(),
    }

    shipment, error = await shipping_service.create_shipment(body.orderId.strip(), address_dict)

    if error:
        status_code, detail = error
        return JSONResponse(status_code=status_code, content=detail)

    return shipment


@router.patch("/{shipment_id}/status")
async def update_status(shipment_id: str, body: ShipmentStatusUpdate):
    """PATCH /api/shipments/{id}/status — advance shipment status."""
    if not body.status or not body.status.strip():
        return JSONResponse(status_code=400, content={"message": "status is required"})

    shipment, error = await shipping_service.update_shipment_status(shipment_id, body.status.strip())

    if error:
        status_code, detail = error
        return JSONResponse(status_code=status_code, content=detail)

    return shipment

