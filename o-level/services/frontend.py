"""shop-frontend: the public API. Calls inventory-service over HTTP for every purchase."""
import os
import random
import time

import requests
from flask import Flask, jsonify, request
from opentelemetry import baggage, context, metrics, trace
from opentelemetry.trace import Status, StatusCode

import telemetry

app = Flask(__name__)
log = telemetry.setup(app)
tracer = trace.get_tracer("a9.frontend")
meter = metrics.get_meter("a9.frontend")
orders = meter.create_counter("shop.orders", unit="{order}", description="Purchase attempts by result")

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory:8081")


@app.get("/buy/<sku>")
def buy(sku: str):
    qty = int(request.args.get("qty", 1))
    tier = request.headers.get("X-User-Tier", "free")

    # Baggage: put the customer tier in the context; it travels to every downstream
    # service in the `baggage` header, next to `traceparent`.
    token = context.attach(baggage.set_baggage("user.tier", tier))
    try:
        span = trace.get_current_span()
        span.set_attribute("shop.sku", sku)
        span.set_attribute("user.tier", tier)
        log.info("purchase request sku=%s qty=%d tier=%s", sku, qty, tier)

        resp = requests.get(f"{INVENTORY_URL}/reserve/{sku}", params={"qty": qty}, timeout=5)
        if resp.status_code != 200:
            reason = resp.json().get("error", "inventory error")
            orders.add(1, {"result": "rejected", "user.tier": tier})
            log.warning("purchase rejected sku=%s: %s", sku, reason)
            return jsonify(error=reason, trace_id=_trace_id()), resp.status_code

        with tracer.start_as_current_span("charge-payment") as pay:
            pay.set_attribute("payment.amount", resp.json()["price"] * qty)
            time.sleep(random.uniform(0.02, 0.06))
            if random.random() < 0.08:
                pay.set_status(Status(StatusCode.ERROR, "card declined"))
                orders.add(1, {"result": "payment_failed", "user.tier": tier})
                log.error("payment declined sku=%s qty=%d", sku, qty)
                return jsonify(error="payment declined", trace_id=_trace_id()), 402

        orders.add(1, {"result": "ok", "user.tier": tier})
        log.info("purchase completed sku=%s qty=%d", sku, qty)
        return jsonify(status="ok", sku=sku, qty=qty, trace_id=_trace_id())
    finally:
        context.detach(token)


def _trace_id() -> str:
    return format(trace.get_current_span().get_span_context().trace_id, "032x")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
