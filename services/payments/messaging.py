"""
Lab 4 — RabbitMQ producer of the Payments service.

After a payment succeeds and the order is PAID, Payments publishes a
ShipmentRequested message to the durable queue `shipping_requests`.
The Shipping service consumes it later, so the customer never waits for
shipment preparation and no request is lost while Shipping is down.

Contract: docs/LAB4_CONTRACTS.md §2.
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_RABBITMQ_URL = "amqp://guest:guest@localhost:5672/%2F"
SHIPPING_QUEUE = "shipping_requests"
MESSAGE_TYPE = "ShipmentRequested"


def build_shipment_requested(order: Dict[str, Any], payment: Dict[str, Any]) -> Dict[str, Any]:
    """Build the ShipmentRequested message from the paid order and its payment."""
    customer = order.get("customer") or {}
    return {
        "messageId": str(uuid.uuid4()),
        "type": MESSAGE_TYPE,
        "orderId": payment["orderId"],
        "paymentId": payment["id"],
        "address": {
            "name": customer.get("name", ""),
            "address": customer.get("address", ""),
            "city": customer.get("city", ""),
        },
        "occurredAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _default_connection_factory(url: str):
    import pika  # imported here so the service still starts if pika is missing

    parameters = pika.URLParameters(url)
    parameters.connection_attempts = 1
    parameters.socket_timeout = 2
    parameters.blocked_connection_timeout = 5
    return pika.BlockingConnection(parameters)


class ShipmentRequestPublisher:
    """
    Keeps one connection and one channel to RabbitMQ and reuses them
    (the handout: do not open a TCP connection per message).

    - The queue is declared durable, non-exclusive, non-auto-delete
      (same flags as the Shipping consumer; declaration is idempotent).
    - Messages are persistent (delivery_mode=2).
    - Publisher confirms are on: publish() returns True only when the
      broker has accepted the message.

    pika's BlockingConnection is not thread-safe, so every call goes
    through a lock. The connection is opened lazily on the first publish,
    so Payments starts normally even when RabbitMQ is down.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        queue: str = SHIPPING_QUEUE,
        connection_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.url = url or os.getenv("RABBITMQ_URL", DEFAULT_RABBITMQ_URL)
        self.queue = queue
        self._connection_factory = connection_factory or _default_connection_factory
        self._connection = None
        self._channel = None
        self._lock = threading.Lock()

    def publish(self, message: Dict[str, Any]) -> bool:
        """Publish one message. Returns True if RabbitMQ confirmed it, False otherwise. Never raises."""
        body = json.dumps(message).encode("utf-8")
        with self._lock:
            # Two attempts: an idle connection may have been closed by the
            # broker (heartbeat timeout); the second attempt reconnects.
            for attempt in (1, 2):
                try:
                    channel = self._ensure_channel()
                    channel.basic_publish(
                        exchange="",
                        routing_key=self.queue,
                        body=body,
                        properties=self._properties(message),
                        mandatory=True,
                    )
                    logger.info(
                        "Published %s %s for order %s",
                        message.get("type"), message.get("messageId"), message.get("orderId"),
                    )
                    return True
                except Exception as exc:  # pika raises many different error types
                    logger.warning(
                        "Publishing %s for order %s failed (attempt %d): %s",
                        message.get("type"), message.get("orderId"), attempt, exc,
                    )
                    self._reset()
        return False

    def close(self) -> None:
        with self._lock:
            self._reset()

    # ── internals ───────────────────────────────────────────────

    def _ensure_channel(self):
        if self._channel is not None and self._channel.is_open:
            return self._channel
        self._reset()
        self._connection = self._connection_factory(self.url)
        channel = self._connection.channel()
        channel.queue_declare(
            queue=self.queue, durable=True, exclusive=False, auto_delete=False
        )
        channel.confirm_delivery()
        self._channel = channel
        return channel

    @staticmethod
    def _properties(message: Dict[str, Any]):
        import pika

        return pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # persistent
            message_id=message.get("messageId"),
            type=message.get("type"),
        )

    def _reset(self) -> None:
        connection, self._connection, self._channel = self._connection, None, None
        if connection is not None:
            try:
                if connection.is_open:
                    connection.close()
            except Exception:
                pass
