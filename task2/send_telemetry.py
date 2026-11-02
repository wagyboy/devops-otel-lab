"""Task 2: send traces and logs to the Collector over OTLP/gRPC (localhost:4317).

Same checkout flow as Task 1, but the exporter is now OTLP instead of the console,
and Python log records are shipped too.
"""
import logging
import random
import time

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

ENDPOINT = "http://localhost:4317"
resource = Resource.create({"service.name": "checkout-demo", "service.version": "1.1.0",
                            "deployment.environment": "docker-lab"})

# Traces: SDK -> BatchSpanProcessor -> OTLP exporter -> Collector
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=ENDPOINT, insecure=True)))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer("a9.checkout")

# Logs: standard logging -> OTel LoggingHandler -> OTLP exporter -> Collector
logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=ENDPOINT, insecure=True)))
set_logger_provider(logger_provider)
log = logging.getLogger("checkout")
log.setLevel(logging.INFO)
log.addHandler(LoggingHandler(logger_provider=logger_provider))
log.addHandler(logging.StreamHandler())


def checkout(order_id: str, items: int) -> None:
    with tracer.start_as_current_span("checkout") as root:
        root.set_attribute("order.id", order_id)
        log.info("checkout started for %s (%d items)", order_id, items)
        with tracer.start_as_current_span("reserve-stock"):
            time.sleep(random.uniform(0.01, 0.03))
        with tracer.start_as_current_span("charge-payment") as pay:
            time.sleep(random.uniform(0.02, 0.05))
            if order_id.endswith("3"):
                pay.set_status(Status(StatusCode.ERROR, "card declined"))
                log.error("payment declined for %s", order_id)
                return
        log.info("order %s completed", order_id)


if __name__ == "__main__":
    for n in range(1, 4):
        checkout(f"A9-200{n}", items=n)
    tracer_provider.shutdown()   # flush both batch processors before exit
    logger_provider.shutdown()
    print("sent 3 traces and their logs to", ENDPOINT)
