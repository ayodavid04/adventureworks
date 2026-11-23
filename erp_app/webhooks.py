"""Webhooks: push each ERP change to the registered URLs as a signed JSON POST.

Headers on every POST:
  X-ERP-Event       order.created | order.updated | customer.updated | test.ping
  X-ERP-Delivery    the delivery id (the same on retries, so a receiver can ignore duplicates)
  X-ERP-Timestamp   when it was sent, Unix seconds
  X-ERP-Signature   sha256=<hex HMAC-SHA256 of "<timestamp>.<raw body>" keyed with the webhook's secret>

A delivery is tried up to 3 times (after 0, 2 and 8 seconds). Anything but a 2xx is a failure.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import queue
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from psycopg.types.json import Jsonb

from . import db

EVENTS = ["order.created", "order.updated", "customer.updated"]
BACKOFF = [0, 2, 8]
_q: queue.Queue = queue.Queue()
_started = False


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def emit(event: str, data: dict) -> int:
    """Queue `event` for every active webhook subscribed to it. Returns how many were queued."""
    hooks = db.rows("select webhook_id from erp_app.webhooks where active and %s = any(events)", (event,))
    for h in hooks:
        _queue(h["webhook_id"], event, data)
    return len(hooks)


def send_test(webhook_id: int) -> uuid.UUID:
    return _queue(webhook_id, "test.ping", {"message": "Test event from AdventureWorks ERP (demo)"})


def _queue(webhook_id: int, event: str, data: dict) -> uuid.UUID:
    delivery_id = uuid.uuid4()
    payload = {"id": str(delivery_id), "event": event,
               "occurred_at": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
               "data": data}
    db.one("insert into erp_app.webhook_deliveries (delivery_id, webhook_id, event, payload) "
           "values (%s, %s, %s, %s) returning delivery_id", (delivery_id, webhook_id, event, Jsonb(payload)))
    start_worker()
    _q.put(delivery_id)
    return delivery_id


def _deliver(delivery_id: uuid.UUID) -> None:
    d = db.one("""select d.payload, d.event, w.url, w.secret from erp_app.webhook_deliveries d
                  join erp_app.webhooks w using (webhook_id) where d.delivery_id = %s""", (delivery_id,))
    if not d:
        return
    body = json.dumps(d["payload"], separators=(",", ":")).encode()
    status, error = None, None
    for attempt, wait in enumerate(BACKOFF, start=1):
        time.sleep(wait)
        ts = str(int(time.time()))
        req = urllib.request.Request(d["url"], data=body, method="POST", headers={
            "Content-Type": "application/json", "User-Agent": "adventureworks-erp-demo/1.0",
            "X-ERP-Event": d["event"], "X-ERP-Delivery": str(delivery_id),
            "X-ERP-Timestamp": ts, "X-ERP-Signature": sign(d["secret"], ts, body)})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                status, error = r.status, None
        except urllib.error.HTTPError as e:
            status, error = e.code, f"HTTP {e.code}"
        except Exception as e:  # connection refused, timeout, bad URL
            status, error = None, str(e)[:300]
        ok = status is not None and 200 <= status < 300
        db.one("""update erp_app.webhook_deliveries set attempts = %s, http_status = %s, last_error = %s,
                  status = %s, delivered_at = case when %s then now() end where delivery_id = %s returning 1""",
               (attempt, status, error, "delivered" if ok else ("failed" if attempt == len(BACKOFF) else "pending"),
                ok, delivery_id))
        if ok:
            return


def _worker() -> None:
    while True:
        delivery_id = _q.get()
        try:
            # each delivery in its own thread, so one slow receiver doesn't hold up the rest
            threading.Thread(target=_deliver, args=(delivery_id,), daemon=True).start()
        finally:
            _q.task_done()


def start_worker() -> None:
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_worker, daemon=True, name="webhook-worker").start()
