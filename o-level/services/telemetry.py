"""Shared OpenTelemetry setup for both services: traces, metrics and logs over OTLP.

The endpoint and service name come from the standard env vars
(OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME), so the code is the same in every service.
"""
import logging
import os

from flask import Flask
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup(app: Flask) -> logging.Logger:
    resource = Resource.create({
        "service.namespace": "a9-shop",
        "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "deployment.environment": "docker-lab",
    })  # service.name is read from OTEL_SERVICE_NAME

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=5000)],
    ))

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)

    # Console logs get otelTraceID/otelSpanID in their format; OTLP log records carry
    # the trace context natively. Both are what makes log <-> trace correlation work.
    # The instrumentor also attaches an OTel LoggingHandler to the root logger, so no
    # handler is added here (adding one too would ship every record twice).
    LoggingInstrumentor().instrument(
        set_logging_format=True,
        logging_format="%(asctime)s %(levelname)s [%(name)s] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] %(message)s",
    )
    log = logging.getLogger(os.getenv("OTEL_SERVICE_NAME", "app"))
    log.setLevel(logging.INFO)

    # Auto-instrumentation: a server span per Flask request, a client span per outgoing
    # requests call, and W3C traceparent + baggage headers injected/extracted for free.
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()
    return log
