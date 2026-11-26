"""Run H3 against an empty, dedicated broker. Orders and Kafka are isolated test doubles."""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import httpx
import pika

import consumer
import database
import shipping_service
from .test_shipping import init_database, message


def worker(path, crash):
    """Pause at basic_ack in the crash child so the parent can observe Unacked."""
    database.DB_PATH = path
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("pika").setLevel(logging.WARNING)

    async def fetch_order(order_id):
        if Path(path).with_suffix(".orders-down").exists():
            return None, (503, {"message": "Orders unavailable"})
        return {"status": "PAID"}, None

    def pause_before_ack(*args, **kwargs):
        print("H3 test child paused after commit and before ACK", flush=True)
        time.sleep(120)
        raise AssertionError("The test should terminate this child before ACK")

    with (
        patch.object(shipping_service, "_fetch_order", fetch_order),
        patch.object(shipping_service, "publish_event"),
    ):
        if crash:
            with patch.object(pika.adapters.blocking_connection.BlockingChannel, "basic_ack", pause_before_ack):
                run_worker()
        else:
            run_worker()


def run_worker():
    service = consumer.ShippingConsumer()
    service.start()
    try:
        sys.stdin.readline()
    finally:
        service.stop()


class H3(unittest.TestCase):
    def setUp(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = folder / "shipping.db"
        self.logs = folder / "consumer.log"
        init_database(self.path)
        self.enterContext(patch.object(database, "DB_PATH", self.path))
        url = os.environ["H3_RABBITMQ_URL"]
        management = os.environ["H3_MANAGEMENT_URL"]
        self.http = self.enterContext(httpx.Client(base_url=management, auth=("guest", "guest")))
        self.connection = self.enterContext(pika.BlockingConnection(pika.URLParameters(url)))
        self.channel = self.connection.channel()
        declared = self.channel.queue_declare(
            queue=consumer.SHIPPING_QUEUE, durable=True, exclusive=False, auto_delete=False
        ).method
        self.assertEqual(
            (declared.message_count, declared.consumer_count), (0, 0),
            "Use an empty, dedicated H3 broker",
        )
        self.channel.confirm_delivery()
        self.message = message()
        self.worker_env = dict(os.environ, RABBITMQ_URL=url)
        self.capture_dir = os.getenv("H3_CAPTURE_DIR")
        if self.capture_dir:
            from playwright.sync_api import sync_playwright

            browser_api = self.enterContext(sync_playwright())
            browser = browser_api.chromium.launch(channel="msedge")
            self.addCleanup(browser.close)
            self.page = browser.new_page(viewport={"width": 1450, "height": 1000})
            self.page.goto(management)
            self.page.locator('input[name="username"]').fill("guest")
            self.page.locator('input[name="password"]').fill("guest")
            self.page.locator('input[type="submit"]').click()
            self.page.get_by_role("link", name="Queues and Streams").wait_for()
            self.page.goto(management.rstrip("/") + "/#/queues/%2F/shipping_requests")
            Path(self.capture_dir).mkdir(parents=True, exist_ok=True)

    def state(self):
        response = self.http.get("/api/queues/%2F/shipping_requests")
        response.raise_for_status()
        queue = response.json()
        return (
            queue.get("messages_ready", 0),
            queue.get("messages_unacknowledged", 0),
            queue.get("consumers", 0),
            queue.get("message_stats", {}).get("ack", 0),
        )

    def wait_for(self, label, predicate):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(0.2)
        logs = self.logs.read_text(encoding="utf-8", errors="replace") if self.logs.exists() else ""
        self.fail(f"{label} timed out; Ready/Unacked/Consumers/ACK={self.state()}\n{logs}")

    def publish(self):
        self.channel.basic_publish(
            exchange="",
            routing_key=consumer.SHIPPING_QUEUE,
            body=json.dumps(self.message).encode(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            mandatory=True,
        )

    def start_worker(self, crash=False):
        with self.logs.open("ab") as log:
            process = subprocess.Popen(
                [sys.executable, "-u", "-m", "tests.h3_rabbitmq", "worker", str(self.path), str(crash)],
                stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, env=self.worker_env,
            )
        self.addCleanup(self.stop_worker, process)
        self.wait_for("Consumer connected", lambda: self.state()[2] == 1)
        return process

    def stop_worker(self, process, crash=False):
        if process.poll() is None:
            try:
                if crash:
                    process.kill()
                else:
                    process.stdin.close()
                process.wait(timeout=10)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
        process.stdin.close()
        self.wait_for("Consumer disconnected", lambda: self.state()[2] == 0)

    def rows(self):
        with closing(database.get_db()) as connection:
            return connection.execute(
                "SELECT id FROM shipments WHERE order_id = ?", (self.message["orderId"],)
            ).fetchall()

    def evidence(self, label, filename=None):
        print(f"\n{label}: Ready/Unacked/Consumers/ACK={self.state()}, SQLite rows={len(self.rows())}", flush=True)
        if self.capture_dir and filename:
            self.page.reload()
            self.page.get_by_role("heading", name="Queue shipping_requests").wait_for()
            self.page.screenshot(path=Path(self.capture_dir) / f"{filename}.png")

    def assert_ack(self, baseline, filename=None, redelivered=False):
        def settled():
            ready, unacked, _, ack = self.state()
            return ready == unacked == 0 and ack == baseline + 1

        self.wait_for("Broker recorded one ACK", settled)
        logs = self.logs.read_text(encoding="utf-8", errors="replace")
        self.assertIn(f"ACK order={self.message['orderId']} redelivered={redelivered}", logs)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.evidence("ACK confirmed", filename)
        print(logs, end="", flush=True)
        return rows[0]["id"]

    def test_1_normal(self):
        self.start_worker()
        baseline = self.state()[3]
        self.publish()
        self.assert_ack(baseline, "h3-1-normal")

    def test_2_shipping_offline(self):
        process = self.start_worker()
        self.stop_worker(process)
        baseline = self.state()[3]
        self.publish()
        self.wait_for("One Ready message offline", lambda: self.state()[:3] == (1, 0, 0))
        self.assertEqual(len(self.rows()), 0)
        self.evidence("Shipping offline", "h3-2-offline")
        self.start_worker()
        self.assert_ack(baseline, "h3-2-restarted")

    def test_3_crash_before_ack(self):
        process = self.start_worker(crash=True)
        baseline = self.state()[3]
        self.publish()
        self.wait_for("Committed message Unacked", lambda: self.state()[:3] == (0, 1, 1) and self.rows())
        original_id = self.rows()[0]["id"]
        self.assertEqual(self.state()[3], baseline)
        self.evidence("After SQLite commit, before crash", "h3-3-unacked")
        self.stop_worker(process, crash=True)
        self.wait_for("Unacked message returned to Ready", lambda: self.state()[:3] == (1, 0, 0))
        self.assertEqual(self.state()[3], baseline)
        self.evidence("After process crash", "h3-3-ready")
        self.start_worker()
        self.assertEqual(self.assert_ack(baseline, "h3-3-redelivered", redelivered=True), original_id)

    def test_4_recovers_after_orders_unavailable(self):
        unavailable = self.path.with_suffix(".orders-down")
        unavailable.touch()
        self.start_worker()
        baseline = self.state()[3]
        self.publish()
        self.wait_for(
            "Consumer interrupted with unacked message",
            lambda: "Orders response=503" in self.logs.read_text(encoding="utf-8"),
        )
        self.assertEqual(len(self.rows()), 0)
        self.assertEqual(self.state()[3], baseline)
        unavailable.unlink()
        self.assert_ack(baseline, redelivered=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(sys.argv[2], sys.argv[3] == "True")
    else:
        unittest.main(verbosity=2)
