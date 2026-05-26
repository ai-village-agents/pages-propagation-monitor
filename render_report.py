#!/usr/bin/env python3
"""Render a minimal static HTML report from monitor output JSON."""

from __future__ import annotations

import argparse
import html
import json
import sys

HEADER_ORDER = [
    "http_status",
    "content-range",
    "content-length",
    "content-encoding",
    "cache-control",
    "age",
    "via",
    "x-served-by",
    "etag",
    "last-modified",
]


def format_headers(headers: dict | None) -> str:
    if not headers:
        return ""
    parts = []
    for key in HEADER_ORDER[1:]:
        val = headers.get(key)
        if val is not None:
            parts.append(f"<div><span class='label'>{html.escape(key)}</span> {html.escape(str(val))}</div>")
    return "".join(parts)


def format_contains(results: list | None, ok_all: bool | None) -> str:
    if not results:
        return ""
    rows = []
    for res in results:
        needle = res.get("needle")
        ok = res.get("ok")
        err = res.get("error")
        status_txt = "ok" if ok else "fail"
        extra = f" (error: {html.escape(str(err))})" if err else ""
        rows.append(f"<div class='contains {status_txt}'>{html.escape(str(needle))}: {status_txt}{extra}</div>")
    if ok_all is not None:
        rows.append(f"<div class='contains summary'>all needles ok: {ok_all}</div>")
    return "".join(rows)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    obj = json.load(open(args.inp, "r", encoding="utf-8"))
    rows = []
    for r in obj.get("results", []):
        ok = r.get("ok")
        probe_type = r.get("probe_type") or "full"
        url = r.get("final_url") or r.get("url")
        contains_results = r.get("contains_results")
        ok_contains_all = r.get("ok_contains_all")

        if probe_type == "range":
            status_parts = []
            for label in ("head", "tail"):
                status_val = r.get(f"range_{label}_http_status")
                if status_val is not None:
                    status_parts.append(f"{label}: {status_val}")
            status_html = "<br>".join(html.escape(str(s)) for s in status_parts) or html.escape(str(r.get("http_status")))
            hash_parts = []
            if r.get("range_head_sha256"):
                hash_parts.append(
                    f"<div><span class='label'>head</span> <code>{html.escape(str(r.get('range_head_sha256')))}</code></div>"
                )
            if r.get("range_tail_sha256"):
                hash_parts.append(
                    f"<div><span class='label'>tail</span> <code>{html.escape(str(r.get('range_tail_sha256')))}</code></div>"
                )
            hash_html = "".join(hash_parts)
            bytes_parts = []
            if r.get("range_head_bytes_read") is not None:
                trunc = " (truncated)" if r.get("range_head_truncated") else ""
                bytes_parts.append(
                    f"<div><span class='label'>head</span> {r.get('range_head_bytes_read')} bytes{trunc}</div>"
                )
            if r.get("range_tail_bytes_read") is not None:
                trunc = " (truncated)" if r.get("range_tail_truncated") else ""
                bytes_parts.append(
                    f"<div><span class='label'>tail</span> {r.get('range_tail_bytes_read')} bytes{trunc}</div>"
                )
            bytes_html = "".join(bytes_parts)
            headers_blocks = []
            for label in ("head", "tail"):
                hdrs = r.get(f"range_{label}_headers")
                if hdrs:
                    headers_blocks.append(
                        f"<div class='hdr-block'><div class='hdr-title'>{label}</div>{format_headers(hdrs)}</div>"
                    )
            headers_html = "".join(headers_blocks)
        else:
            status_html = html.escape(str(r.get("http_status")))
            hash_html = f"<code>{html.escape(str(r.get('sha256')))}</code>"
            bytes_html = f"{html.escape(str(r.get('bytes_read')))} bytes"
            if r.get("truncated"):
                bytes_html += " (truncated)"
            headers_html = format_headers(r.get("headers") or {})

        contains_html = format_contains(contains_results, ok_contains_all)

        headers_html += f"<div class='hdr-meta'>Accept-Encoding: {html.escape(str(r.get('accept_encoding')))}</div>"

        rows.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('name')))}</td>"
            f"<td><a href=\"{html.escape(url)}\">link</a></td>"
            f"<td>{status_html}</td>"
            f"<td>{'OK' if ok else 'FAIL'}</td>"
            f"<td>{html.escape(probe_type)}</td>"
            f"<td>{hash_html}</td>"
            f"<td>{bytes_html}</td>"
            f"<td>{headers_html}</td>"
            f"<td>{contains_html}</td>"
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
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; background: #f9fafb; color: #0f172a; }
    table { border-collapse: collapse; width: 100%; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08); background: white; }
    th, td { border: 1px solid #e5e7eb; padding: 10px; vertical-align: top; }
    th { background: #f1f5f9; text-align: left; font-weight: 600; }
    tr:nth-child(even) { background: #f8fafc; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; word-break: break-all; white-space: pre-wrap; }
    .label { display: inline-block; font-size: 11px; color: #475569; text-transform: lowercase; margin-right: 4px; padding: 2px 6px; border-radius: 999px; background: #e2e8f0; }
    .hdr-block { margin-bottom: 8px; }
    .hdr-title { font-weight: 600; margin-bottom: 2px; text-transform: capitalize; }
    .hdr-meta { margin-top: 6px; color: #475569; font-size: 12px; }
    .contains.ok { color: #0f5132; }
    .contains.fail { color: #b91c1c; }
    .contains.summary { margin-top: 6px; font-weight: 600; }
    a { color: #0ea5e9; }
  </style>
</head>
<body>
  <h1>Pages Propagation Monitor</h1>
  <p>Generated at: <code>__GEN__</code></p>
  <table>
    <thead>
      <tr>
        <th>Name</th><th>URL</th><th>Status</th><th>OK</th><th>Probe</th><th>Hashes</th><th>Bytes</th><th>Headers</th><th>Contains</th>
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
