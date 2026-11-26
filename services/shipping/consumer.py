"""Consume the Payments queue defined in docs/LAB4_CONTRACTS.md §2."""

import asyncio
import logging
import os
from threading import Event, Thread

import pika
from pydantic import ValidationError

from schemas import ShipmentRequested
from shipping_service import create_shipment

logger = logging.getLogger("uvicorn.error").getChild("shipping.rabbitmq")
SHIPPING_QUEUE = "shipping_requests"
DEFAULT_RABBITMQ_URL = "amqp://guest:guest@localhost:5672/%2F"


class ShipmentRetry(Exception):
    """Close the connection without acknowledging the current delivery."""


def handle_delivery(channel, method, properties, body):
    try:
        request = ShipmentRequested.model_validate_json(body)
    except ValidationError as exc:
        logger.warning("Rejected invalid ShipmentRequested (%s validation errors)", exc.error_count())
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    logger.info(
        "Received ShipmentRequested order=%s message=%s redelivered=%s",
        request.orderId, request.messageId, method.redelivered,
    )
    shipment, error, created = asyncio.run(
        create_shipment(request.orderId, request.address.model_dump())
    )
    if error:
        status, _ = error
        if status in (404, 409):
            logger.warning("Rejected ShipmentRequested order=%s Orders status=%s", request.orderId, status)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        raise ShipmentRetry(f"order={request.orderId}, Orders response={status}")

    logger.info("Shipment persisted order=%s shipment=%s created=%s", request.orderId, shipment["id"], created)
    channel.basic_ack(delivery_tag=method.delivery_tag)
    logger.info("ACK order=%s redelivered=%s", request.orderId, method.redelivered)


class ShippingConsumer:
    def __init__(self):
        self._stop = Event()
        self._thread = Thread(target=self._run, name="shipping-rabbitmq")

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()

    def _run(self):
        while not self._stop.is_set():
            try:
                parameters = pika.URLParameters(os.getenv("RABBITMQ_URL", DEFAULT_RABBITMQ_URL))
                parameters.connection_attempts = 1
                parameters.socket_timeout = 2
                parameters.stack_timeout = 5
                parameters.blocked_connection_timeout = 5
                with pika.BlockingConnection(parameters) as connection:
                    channel = connection.channel()
                    channel.queue_declare(
                        queue=SHIPPING_QUEUE, durable=True, exclusive=False, auto_delete=False
                    )
                    channel.basic_qos(prefetch_count=1)
                    channel.basic_consume(
                        queue=SHIPPING_QUEUE, on_message_callback=handle_delivery, auto_ack=False
                    )
                    logger.info("Listening on %s", SHIPPING_QUEUE)
                    while not self._stop.is_set():
                        connection.process_data_events(time_limit=0.5)
            except Exception:
                logger.exception("RabbitMQ consumer interrupted. Unacked deliveries will be redelivered")
                self._stop.wait(3)
