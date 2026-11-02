# DevOps A9: Observability with OpenTelemetry

Owner: 陳致安 (B11309058) · Course: DevOps

| Folder | Level | What it shows |
| --- | --- | --- |
| `task1/` | A | OpenTelemetry SDK with `ConsoleSpanExporter`: a 7-span trace with nesting, attributes, events and an error |
| `task2/` | E | Dockerized Collector (`otel/opentelemetry-collector-contrib:0.164.0`): OTLP on 4317 → memory_limiter, resource, batch → console + local file, for traces and logs |
| `o-level/` | O | Two Flask services with context propagation and baggage; a Collector with three pipelines + spanmetrics connector → Jaeger, Prometheus, log file; log ↔ trace correlation |
| `screenshots/` | | Every figure used in the report |
| `build/` | | Report source (`report.md`) and the scripts that build the PDF and capture screenshots |

## Run it

Requirements: Python 3.10+, Docker Desktop.

```bash
python -m venv .venv
.venv/Scripts/pip install opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-instrumentation-flask opentelemetry-instrumentation-requests opentelemetry-instrumentation-logging flask requests
```

**Task 1:** console output

```bash
cd task1 && ../.venv/Scripts/python console_demo.py --compact
```

**Task 2:** Collector → console + file

```bash
cd task2 && docker compose up -d
../.venv/Scripts/python send_telemetry.py
docker logs otel-collector          # debug exporter
cat output/telemetry.jsonl          # file exporter
docker compose down
```

**O level:** two services, Jaeger, Prometheus

```bash
cd o-level && docker compose up -d --build
../.venv/Scripts/python load.py 120
../.venv/Scripts/python correlate.py --errors      # trace ids of WARN/ERROR logs
../.venv/Scripts/python correlate.py <trace_id>    # all logs of one request, across services
docker compose down
```

| UI | URL |
| --- | --- |
| shop-frontend | http://localhost:8080/buy/SKU-100?qty=1 (header `X-User-Tier: premium` optional) |
| Jaeger | http://localhost:16686 |
| Prometheus | http://localhost:19090 |
| Collector metrics endpoint | http://localhost:18889/metrics |

Host ports 18889 and 19090 are used because Windows (Hyper-V/WSL) reserved 8889 and 9090 on the machine this was built on.
