"""inventory-service: owns stock levels. Only called by shop-frontend."""
import random
import threading
import time

from flask import Flask, jsonify, request
from opentelemetry import baggage, metrics, trace
from opentelemetry.metrics import Observation

import telemetry

app = Flask(__name__)
log = telemetry.setup(app)
tracer = trace.get_tracer("a9.inventory")
meter = metrics.get_meter("a9.inventory")

PRICES = {"SKU-100": 120, "SKU-200": 450, "SKU-300": 990}
stock = {"SKU-100": 3000, "SKU-200": 1500, "SKU-300": 150}
lock = threading.Lock()

meter.create_observable_gauge(
    "inventory.stock.level", unit="{item}", description="Items left per SKU",
    callbacks=[lambda _: [Observation(n, {"sku": s}) for s, n in stock.items()]],
)


@app.get("/reserve/<sku>")
def reserve(sku: str):
    qty = int(request.args.get("qty", 1))
    # The tier was set by shop-frontend; it arrived here in the baggage header.
    tier = baggage.get_baggage("user.tier") or "unknown"
    span = trace.get_current_span()
    span.set_attribute("user.tier", tier)
    span.set_attribute("shop.sku", sku)

    if sku not in PRICES:
        log.warning("unknown sku %s", sku)
        return jsonify(error=f"unknown sku {sku}"), 404

    with tracer.start_as_current_span("db.reserve-stock") as db:
        db.set_attribute("db.system", "postgresql")
        db.set_attribute("db.operation", "UPDATE")
        # Premium users get a dedicated (faster) replica; free users share one.
        time.sleep(random.uniform(0.005, 0.02) if tier == "premium" else random.uniform(0.03, 0.12))
        with lock:
            if stock[sku] < qty:
                db.add_event("insufficient stock", {"requested": qty, "available": stock[sku]})
                log.warning("insufficient stock sku=%s requested=%d available=%d", sku, qty, stock[sku])
                return jsonify(error="out of stock"), 409
            stock[sku] -= qty

    log.info("reserved sku=%s qty=%d tier=%s left=%d", sku, qty, tier, stock[sku])
    return jsonify(sku=sku, qty=qty, price=PRICES[sku])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
