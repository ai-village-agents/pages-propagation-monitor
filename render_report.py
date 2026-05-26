#!/usr/bin/env python3
"""Render a minimal static HTML report from monitor output JSON."""

from __future__ import annotations

import argparse
import html
import json
import sys


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    obj = json.load(open(args.inp, "r", encoding="utf-8"))
    rows = []
    for r in obj.get("results", []):
        status = r.get("http_status")
        ok = r.get("ok")
        sha = r.get("sha256")
        lm = (r.get("headers") or {}).get("last-modified")
        enc = r.get("accept_encoding")
        url = r.get("final_url") or r.get("url")
        contains = r.get("contains")
        contains_txt = ""
        if isinstance(contains, dict):
            contains_txt = f"{contains.get('needle')}: {contains.get('ok')}"
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('name')))}</td>"
            f"<td><a href=\"{html.escape(url)}\">link</a></td>"
            f"<td>{html.escape(str(status))}</td>"
            f"<td>{'OK' if ok else 'FAIL'}</td>"
            f"<td><code>{html.escape(str(sha))}</code></td>"
            f"<td>{html.escape(str(lm))}</td>"
            f"<td>{html.escape(str(enc))}</td>"
            f"<td>{html.escape(contains_txt)}</td>"
            "</tr>"
        )

    gen = obj.get("generated_at")

    html_doc = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pages Propagation Monitor</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
    th { background: #f6f6f6; text-align: left; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
  </style>
</head>
<body>
  <h1>Pages Propagation Monitor</h1>
  <p>Generated at: <code>__GEN__</code></p>
  <table>
    <thead>
      <tr>
        <th>Name</th><th>URL</th><th>Status</th><th>OK</th><th>SHA-256</th><th>Last-Modified</th><th>Accept-Encoding</th><th>Contains</th>
      </tr>
    </thead>
    <tbody>
      __ROWS__
    </tbody>
  </table>
</body>
</html>
"""

    html_doc = html_doc.replace("__GEN__", html.escape(str(gen))).replace("__ROWS__", "\n".join(rows))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
