"""How Orders talks to Inventory (LAB 4 - high-performance communication).

Two interchangeable gateways with the same methods:
  * GrpcInventoryGateway (default): gRPC client of inventory.InventoryService,
    contract in proto/inventory.proto.
  * RestInventoryGateway: the previous REST/JSON calls, kept as a fallback and
    for the REST vs gRPC comparison (INVENTORY_TRANSPORT=rest).

Both raise fastapi.HTTPException, so the order workflow and the REST API that
Orders exposes are unchanged.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Protocol

import grpc
import httpx
from fastapi import HTTPException

import inventory_pb2
import inventory_pb2_grpc
from service import _release_inventory, _reserve_inventory

logger = logging.getLogger(__name__)

Items = List[Dict[str, int]]


class InventoryGateway(Protocol):
    async def ensure_available(self, items: Items) -> None: ...
    async def reserve(self, items: Items) -> None: ...
    async def release(self, items: Items) -> None: ...
    async def close(self) -> None: ...


class RestInventoryGateway:
    """REST/JSON over HTTP/1.1 (behaviour before LAB 4)."""

    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self._client = client
        self._base_url = base_url

    async def ensure_available(self, items: Items) -> None:
        # The atomic reservation already checks the stock.
        return None

    async def reserve(self, items: Items) -> None:
        await _reserve_inventory(self._client, self._base_url, items)

    async def release(self, items: Items) -> None:
        await _release_inventory(self._client, self._base_url, items)

    async def close(self) -> None:
        return None  # the shared httpx client is closed by the app


# gRPC status code -> HTTP status returned by the Orders REST API
_HTTP_STATUS = {
    grpc.StatusCode.INVALID_ARGUMENT: 400,
    grpc.StatusCode.NOT_FOUND: 404,
    grpc.StatusCode.FAILED_PRECONDITION: 409,
    grpc.StatusCode.UNAVAILABLE: 503,
    grpc.StatusCode.DEADLINE_EXCEEDED: 504,
}


def _to_http_error(error: grpc.aio.AioRpcError, operation: str) -> HTTPException:
    code = error.code()
    if code == grpc.StatusCode.UNAVAILABLE:
        logger.warning("Inventory gRPC %s: service unavailable", operation)
        return HTTPException(status_code=503, detail="The inventory service is unavailable.")
    if code == grpc.StatusCode.DEADLINE_EXCEEDED:
        logger.warning("Inventory gRPC %s: deadline exceeded", operation)
        return HTTPException(status_code=504, detail="The inventory service timed out.")
    if code in _HTTP_STATUS:
        return HTTPException(status_code=_HTTP_STATUS[code], detail=error.details() or "Inventory error.")
    logger.error("Inventory gRPC %s failed: %s %s", operation, code, error.details())
    return HTTPException(status_code=502, detail="The inventory service returned an error.")


def _stock_request(items: Items) -> inventory_pb2.StockRequest:
    return inventory_pb2.StockRequest(items=[
        inventory_pb2.StockItem(productId=str(item["productId"]), quantity=item["quantity"])
        for item in items
    ])


class GrpcInventoryGateway:
    """gRPC client: Protobuf over one persistent HTTP/2 channel."""

    def __init__(self, address: str, timeout: float = 2.0,
                 channel: Optional[grpc.aio.Channel] = None):
        self.address = address
        self._timeout = timeout
        self._channel = channel or grpc.aio.insecure_channel(address)
        self._stub = inventory_pb2_grpc.InventoryServiceStub(self._channel)

    async def check_availability(self, product_id: int, quantity: int) -> inventory_pb2.AvailabilityResponse:
        request = inventory_pb2.AvailabilityRequest(productId=str(product_id), quantity=quantity)
        # Read-only, so one retry on a transient UNAVAILABLE is safe.
        for attempt in (1, 2):
            try:
                return await self._stub.CheckAvailability(request, timeout=self._timeout)
            except grpc.aio.AioRpcError as error:
                if error.code() == grpc.StatusCode.UNAVAILABLE and attempt == 1:
                    await asyncio.sleep(0.2)
                    continue
                raise _to_http_error(error, "CheckAvailability")

    async def ensure_available(self, items: Items) -> None:
        responses = await asyncio.gather(*(
            self.check_availability(item["productId"], item["quantity"]) for item in items
        ))
        for item, response in zip(items, responses):
            if not response.available:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Insufficient stock for product {item['productId']}: "
                        f"requested {item['quantity']}, available {response.availableQuantity}."
                    ),
                )

    async def reserve(self, items: Items) -> None:
        # Modifies stock: never retried automatically.
        try:
            await self._stub.ReserveStock(_stock_request(items), timeout=self._timeout)
        except grpc.aio.AioRpcError as error:
            raise _to_http_error(error, "ReserveStock")

    async def release(self, items: Items) -> None:
        try:
            await self._stub.ReleaseStock(_stock_request(items), timeout=self._timeout)
        except grpc.aio.AioRpcError as error:
            raise _to_http_error(error, "ReleaseStock")

    async def close(self) -> None:
        await self._channel.close()
