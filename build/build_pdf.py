"""Build the A8 report PDF: report.md -> report.html -> PDF via headless Edge."""
import html
import pathlib
import re
import subprocess
import sys

import markdown

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "report.md"
OUT_HTML = HERE / "report.html"
OUT_PDF = HERE.parent / "A8_陳致安_Opentelemetry.pdf"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

CSS = """
@page {
  size: A4 portrait;
  margin: 15mm 15mm 16mm 15mm;
  @bottom-center { content: "Page " counter(page) " of " counter(pages); font: 9pt 'Segoe UI', sans-serif; color: #666; }
}
* { box-sizing: border-box; }
body { font: 10pt/1.45 'Segoe UI', 'Microsoft JhengHei', sans-serif; color: #1a1a1a; margin: 0; }
h1 { font-size: 18pt; margin: 0 0 6pt; }
h2 { font-size: 14pt; margin: 16pt 0 6pt; padding-bottom: 3pt; border-bottom: 1.5px solid #333; break-after: avoid; }
h2.newpage { break-before: page; margin-top: 0; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; break-after: avoid; }
p, li { margin: 3pt 0; }
a { color: #0b57d0; text-decoration: none; }
code { font: 8.8pt Consolas, monospace; background: #f1f3f4; padding: 0 2pt; border-radius: 2px; }
pre { background: #f6f8fa; border: 1px solid #ddd; border-radius: 4px; padding: 5pt 8pt;
      white-space: pre-wrap; word-break: break-word; break-inside: avoid; margin: 5pt 0; }
pre code { background: none; padding: 0; font-size: 8.2pt; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0 8pt; font-size: 8.8pt; break-inside: avoid; }
th, td { border: 1px solid #c8c8c8; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #eef1f4; }
figure { margin: 6pt 0 10pt; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; max-height: 86mm; border: 1px solid #ccc; }
figure img[src*="dependencies"] { max-height: 52mm; }
figcaption { font-size: 8.3pt; color: #555; margin-top: 2pt; }
.meta { color: #333; margin-bottom: 8pt; }
"""

# Sections that start on a new page (by heading text prefix).
NEW_PAGE = ()


def main() -> int:
    body = markdown.markdown(
        SRC.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    )

    n = {"fig": 0}

    def to_figure(m: re.Match) -> str:
        n["fig"] += 1
        alt = html.unescape(m.group("alt"))
        return (
            f'<figure><img src="{m.group("src")}" alt="{html.escape(alt)}">'
            f"<figcaption>Figure {n['fig']}. {html.escape(alt)}</figcaption></figure>"
        )

    body = re.sub(r'<p><img alt="(?P<alt>[^"]*)" src="(?P<src>[^"]+)"\s*/?></p>', to_figure, body)
    body = re.sub(
        r"<h2>(\d+\. )",
        lambda m: (f'<h2 class="newpage">{m.group(1)}' if m.group(1) in NEW_PAGE else f"<h2>{m.group(1)}"),
        body,
    )
    body = body.replace("<p><strong>Name:</strong>", '<p class="meta"><strong>Name:</strong>', 1)

    missing = [s for s in re.findall(r'<img src="([^"]+)"', body) if not (HERE / s).exists()]
    if missing:
        print("Missing images:", *missing, sep="\n  ")
        return 1

    OUT_HTML.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>A8 OpenTelemetry Report</title><style>{CSS}</style></head><body>{body}</body></html>",
        encoding="utf-8",
    )
    print(f"HTML written with {n['fig']} figures")
    subprocess.run(
        [EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header",
         "--virtual-time-budget=15000", f"--print-to-pdf={OUT_PDF}", OUT_HTML.as_uri()],
        check=True, timeout=180,
    )
    print("PDF written:", OUT_PDF, OUT_PDF.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
