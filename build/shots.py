"""Capture Jaeger / Prometheus screenshots with Playwright driving the installed Edge."""
import pathlib
import sys
import urllib.parse

from playwright.sync_api import sync_playwright

A9 = pathlib.Path(__file__).resolve().parent.parent
OUT = A9 / "screenshots"
T402 = (A9 / "o-level" / "t402.txt").read_text().strip()
JAEGER = "http://localhost:16686"
PROM = "http://localhost:19090"


def prom_graph(expr: str, rng: str = "5m") -> str:
    return f"{PROM}/query?" + urllib.parse.urlencode(
        {"g0.expr": expr, "g0.tab": "graph", "g0.range_input": rng, "g0.show_tree": "0"})


def prom_table(expr: str) -> str:
    return f"{PROM}/query?" + urllib.parse.urlencode({"g0.expr": expr, "g0.tab": "table"})


which = set(sys.argv[1:])
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge")
    page = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1)

    def go(url, wait=2500):
        page.goto(url, wait_until="load")
        page.wait_for_timeout(wait)

    if not which or "search" in which:
        go(f"{JAEGER}/search?service=shop-frontend&limit=15&lookback=1h", 3500)
        page.screenshot(path=OUT / "O1-jaeger-search.png")

    if not which or "trace" in which:
        go(f"{JAEGER}/trace/{T402}")
        page.get_by_text("GET /reserve/<sku>", exact=False).first.click()
        page.wait_for_timeout(800)
        page.get_by_text("Attributes:", exact=False).first.click()
        page.wait_for_timeout(800)
        page.screenshot(path=OUT / "O1-jaeger-trace-baggage.png", full_page=True)
        go(f"{JAEGER}/trace/{T402}")
        page.get_by_text("charge-payment", exact=False).first.click()
        page.wait_for_timeout(800)
        page.screenshot(path=OUT / "O2-jaeger-error-span.png", full_page=True)

    if not which or "deps" in which:
        go(f"{JAEGER}/dependencies", 4000)
        page.screenshot(path=OUT / "O1-jaeger-dependencies.png")

    if not which or "prom" in which:
        page.set_viewport_size({"width": 1600, "height": 1000})
        go(f"{PROM}/targets")
        page.screenshot(path=OUT / "O2-prom-targets.png")
        go(prom_graph('sum by (user_tier) (rate(traces_span_metrics_duration_milliseconds_sum{service_name="inventory-service", span_kind="SPAN_KIND_SERVER"}[2m])) / sum by (user_tier) (rate(traces_span_metrics_duration_milliseconds_count{service_name="inventory-service", span_kind="SPAN_KIND_SERVER"}[2m]))'), 4000)
        page.screenshot(path=OUT / "O2-prom-latency-by-tier.png", full_page=True)
        go(prom_graph('sum by (result) (rate(shop_orders_total[2m]))'), 4000)
        page.screenshot(path=OUT / "O2-prom-orders-rate.png", full_page=True)
        go(prom_graph('inventory_stock_level'), 4000)
        page.screenshot(path=OUT / "O2-prom-stock.png", full_page=True)
        go(prom_table('sum by (service_name, span_name, status_code) (traces_span_metrics_calls_total)'), 3000)
        page.screenshot(path=OUT / "O2-prom-spanmetrics-table.png")

    browser.close()
print("done")
