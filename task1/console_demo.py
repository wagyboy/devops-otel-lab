"""Task 1: OpenTelemetry SDK with console output.

Simulates checking out an order. Each step is a span; nested steps become child
spans, so the console output shows one trace ID shared by the whole hierarchy.

  python console_demo.py            # full JSON for every span (ConsoleSpanExporter default)
  python console_demo.py --compact  # one line per span: name, trace id, span id, parent
"""
import random
import sys
import time

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode


def compact(span) -> str:
    ctx = span.get_span_context()
    parent = f"{span.parent.span_id:016x}" if span.parent else "(root)"
    ms = (span.end_time - span.start_time) / 1e6
    return (f"{span.name:<18} trace={ctx.trace_id:032x} span={ctx.span_id:016x} "
            f"parent={parent:<16} {ms:7.1f} ms  {span.status.status_code.name}\n")


# 1. Tracer provider: owns the resource (who is sending) and the span processors.
provider = TracerProvider(resource=Resource.create({
    "service.name": "checkout-demo",
    "service.version": "1.0.0",
    "deployment.environment": "local",
}))

# 2. Exporter: where finished spans go. Here: stdout. SimpleSpanProcessor exports
#    each span the moment it ends (fine for a demo; production uses BatchSpanProcessor).
exporter = ConsoleSpanExporter(formatter=compact) if "--compact" in sys.argv else ConsoleSpanExporter()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("a9.checkout")


def work(low: float, high: float) -> None:
    time.sleep(random.uniform(low, high))


def checkout(order_id: str, items: int) -> None:
    with tracer.start_as_current_span("checkout") as root:
        root.set_attribute("order.id", order_id)
        root.set_attribute("order.items", items)

        with tracer.start_as_current_span("validate-cart"):
            work(0.01, 0.02)

        with tracer.start_as_current_span("reserve-stock") as span:
            span.set_attribute("warehouse", "TPE-1")
            for sku in range(items):
                with tracer.start_as_current_span("db.update-stock") as db:
                    db.set_attribute("db.system", "sqlite")
                    db.set_attribute("sku", f"SKU-{100 + sku}")
                    work(0.005, 0.01)

        with tracer.start_as_current_span("charge-payment") as pay:
            pay.set_attribute("payment.method", "card")
            pay.add_event("first attempt timed out", {"retry.after_ms": 20})
            work(0.02, 0.03)
            pay.add_event("charged")

        with tracer.start_as_current_span("send-email") as mail:
            try:
                raise ConnectionError("SMTP server unreachable")
            except ConnectionError as exc:
                # The order still succeeds; the failed side step is recorded on its own span.
                mail.record_exception(exc)
                mail.set_status(Status(StatusCode.ERROR, str(exc)))


if __name__ == "__main__":
    checkout("A9-1001", items=2)
    provider.shutdown()
