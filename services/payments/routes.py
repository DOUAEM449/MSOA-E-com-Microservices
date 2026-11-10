from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from schemas import PaymentCreate
import payments_service

router = APIRouter(prefix="/api/payments")


@router.get("")
def list_payments():
    """GET /api/payments — list all payments."""
    return payments_service.list_payments()


@router.get("/order/{order_id}")
def get_payment_by_order(order_id: str):
    """GET /api/payments/order/{orderId} — payment for a specific order."""
    payment = payments_service.get_payment_by_order(order_id)
    if not payment:
        return JSONResponse(status_code=404, content={"message": f"No payment found for order {order_id}"})
    return payment


@router.post("", status_code=201)
async def create_payment(body: PaymentCreate):
    """POST /api/payments — create a payment."""
    if not body.orderId or not body.orderId.strip():
        return JSONResponse(status_code=400, content={"message": "orderId is required"})
    if not body.method or not body.method.strip():
        return JSONResponse(status_code=400, content={"message": "method is required"})

    payment, error = await payments_service.create_payment(body.orderId.strip(), body.method.strip())

    if error:
        status_code, detail = error
        return JSONResponse(status_code=status_code, content=detail)

    return payment

