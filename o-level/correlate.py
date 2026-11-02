"""Log <-> trace correlation: print every log line the Collector stored for one trace.

  python correlate.py <trace_id>      # logs of that trace, from all services
  python correlate.py --errors        # trace ids of all ERROR/WARN logs, to paste into Jaeger
"""
import json
import pathlib
import sys

LOGS = pathlib.Path(__file__).parent / "output" / "logs.jsonl"


def records():
    for line in LOGS.read_text(encoding="utf-8").splitlines():
        for rl in json.loads(line)["resourceLogs"]:
            attrs = {a["key"]: a["value"].get("stringValue") for a in rl["resource"]["attributes"]}
            for sl in rl["scopeLogs"]:
                for rec in sl["logRecords"]:
                    yield attrs.get("service.name"), rec


if sys.argv[1:] == ["--errors"]:
    for service, rec in records():
        if rec.get("severityNumber", 0) >= 13:  # WARN and above
            print(f"{rec.get('traceId', '-')}  {service:<18} {rec['severityText']:<7} {rec['body']['stringValue']}")
else:
    wanted = sys.argv[1].lower()
    hits = sorted((rec["timeUnixNano"], service, rec) for service, rec in records() if rec.get("traceId") == wanted)
    print(f"{len(hits)} log records for trace {wanted}")
    for _, service, rec in hits:
        print(f"  {service:<18} span={rec.get('spanId')} {rec['severityText']:<7} {rec['body']['stringValue']}")
