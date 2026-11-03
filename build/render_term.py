"""Render saved command output as terminal-style PNGs (real output, captured during the runs)."""
import html
import json
import re
import pathlib

from playwright.sync_api import sync_playwright

A9 = pathlib.Path(__file__).resolve().parent.parent
OUT = A9 / "screenshots"
T1, T2, O = A9 / "task1", A9 / "task2", A9 / "o-level"


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8").rstrip("\n")


def cut(text: str, width: int = 150) -> str:
    return "\n".join(l if len(l) <= width else l[: width - 1] + "…" for l in text.splitlines())


def spans_json(text: str) -> list[str]:
    # ConsoleSpanExporter writes indented JSON objects back to back; decode them one at a time.
    dec, pos, out = json.JSONDecoder(), 0, []
    while (pos := text.find("{", pos)) != -1:
        obj, end = dec.raw_decode(text, pos)
        out.append(json.dumps(obj, indent=4, ensure_ascii=False))
        pos = end
    return out


def file_export_excerpt() -> str:
    first = json.loads(read(T2 / "output" / "telemetry.jsonl").splitlines()[0])
    rl = first["resourceLogs"][0]
    rec = dict(rl["scopeLogs"][0]["logRecords"][-1])
    rec["attributes"] = rec["attributes"][1:]  # drop the local file path attribute
    keep = {"resourceLogs": [{"resource": {"attributes": [a for a in rl["resource"]["attributes"]
                                                           if a["key"] in ("service.name", "service.version", "collector.name")]},
                              "scopeLogs": [{"scope": rl["scopeLogs"][0]["scope"], "logRecords": [rec]}]}]}
    text = json.dumps(keep, indent=2, ensure_ascii=False)
    # one line per attribute and per body, like a compact pretty-printer would show them
    text = re.sub(r'\{\s+"key": "([^"]+)",\s+"value": \{\s+"(\w+)": ("[^"]*"|\S+)\s+\}\s+\}', r'{"key": "\1", "value": {"\2": \3}}', text)
    return re.sub(r'"body": \{\s+"stringValue": ("[^"]*")\s+\}', r'"body": {"stringValue": \1}', text)


full = spans_json(read(T1 / "out_full.txt"))
send_email = next(s for s in full if '"name": "send-email"' in s)
send_email = send_email.split('"exception.stacktrace"')[0] + '"exception.stacktrace": "Traceback (most recent call last): …"\n            } } ], …'
checkout = next(s for s in full if '"name": "checkout"' in s)
collector = read(T2 / "out_collector.log").splitlines()
t409, t402 = read(O / "t409.txt"), read(O / "t402.txt")
# `docker compose up` prints each progress line more than once; keep the first of each run
up = read(T2 / "out_up.txt").splitlines()
up_lines = "\n".join(l for i, l in enumerate(up) if i == 0 or l.strip() != up[i - 1].strip())
errors_tail = "\n".join(read(O / "out_errors.txt").splitlines()[-6:])

SCREENS = {
    "T1-console-compact.png": [
        ("python console_demo.py --compact", read(T1 / "out_compact.txt")),
    ],
    "T1-console-json.png": [
        ("python console_demo.py   # default ConsoleSpanExporter, 2 of 7 spans shown", send_email + "\n" + checkout.split('"resource"')[0] + "…\n}"),
    ],
    "T2-run.png": [
        ("docker compose up -d", up_lines),
        ("docker compose ps", read(T2 / "out_docker_ps.txt")),
        ("curl -s localhost:13133", read(T2 / "out_health.txt")),
        ("python send_telemetry.py", read(T2 / "out_send.txt")),
        ("ls -l output/", read(T2 / "out_ls.txt")),
    ],
    "T2-collector-debug.png": [
        ("docker logs otel-collector   # debug exporter, excerpt",
         cut("\n".join(collector[12:14]) + "\n…\n" + "\n".join(collector[21:25]) + "\n…\n" + "\n".join(collector[93:106])
             + "\n…\n" + "\n".join(collector[148:163]), 130)),
    ],
    "T2-file-export.png": [
        ("python -m json.tool output/telemetry.jsonl   # file exporter, one log record", file_export_excerpt()),
    ],
    "O-stack-ps.png": [
        ("docker compose ps", read(O / "out_compose_ps.txt")),
        ('curl -s -H "X-User-Tier: premium" "localhost:8080/buy/SKU-200?qty=2"', read(O / "out_first_request.json")),
        ("python load.py 150", read(O / "out_load.txt")),
    ],
    "O2-correlate.png": [
        ("python correlate.py --errors | tail -6", errors_tail),
        (f"python correlate.py {t409}", read(O / "out_correlate_409.txt")),
        (f"python correlate.py {t402}", read(O / "out_correlate_402.txt")),
        (f"docker compose logs --no-log-prefix frontend inventory | grep {t402}", cut(read(O / "out_console_logs.txt"), 175)),
    ],
}

CSS = """
body { margin: 0; background: #fff; }
.term { display: inline-block; min-width: 1100px; background: #0c0c0c; border-radius: 8px; overflow: hidden;
        font: 13px/1.38 'Cascadia Mono', Consolas, monospace; color: #cccccc; }
.bar { background: #2b2b2b; color: #bbb; font: 12px 'Segoe UI', sans-serif; padding: 6px 12px; }
.bar b { color: #eee; font-weight: 600; }
pre { margin: 0; padding: 10px 14px 12px; white-space: pre; }
.cmd { color: #6ee7a7; } .ps { color: #61afef; }
"""

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge")
    page = browser.new_page(viewport={"width": 1500, "height": 900}, device_scale_factor=1.5)
    for name, blocks in SCREENS.items():
        cwd = {"T1": "task1", "T2": "task2"}.get(name[:2], "o-level")
        body = "\n".join(f'<span class="ps">PS A9\\{cwd}&gt;</span> <span class="cmd">{html.escape(c)}</span>\n{html.escape(o)}'
                         for c, o in blocks)
        page.set_content(f'<html><head><style>{CSS}</style></head><body><div class="term">'
                         f'<div class="bar"><b>Terminal</b> — {cwd}</div><pre>{body}</pre></div></body></html>')
        page.locator(".term").screenshot(path=OUT / name)
        print("wrote", name)
    browser.close()
