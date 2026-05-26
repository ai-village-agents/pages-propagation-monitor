#!/usr/bin/env python3
"""Fetch URLs with Accept-Encoding: identity, compute sha256, and save a JSON report."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import urllib.request

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


DEFAULT_UA = "pages-propagation-monitor/0.1 (+https://github.com/ai-village-agents/pages-propagation-monitor)"
HEADER_KEYS = [
    "cache-control",
    "content-type",
    "content-encoding",
    "etag",
    "last-modified",
    "age",
    "via",
    "x-served-by",
]
RANGE_HEADER_KEYS = HEADER_KEYS + ["content-length", "content-range"]


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_hex(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _read_limited(resp, max_bytes: int):
    data = resp.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    return data, truncated


def fetch_full(
    url: str, *, accept_encoding: str, timeout: float, max_bytes: int, user_agent: str
):
    req = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": accept_encoding,
            "User-Agent": user_agent,
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", None)
        headers = {k.lower(): v for k, v in dict(resp.headers).items()}
        data, truncated = _read_limited(resp, max_bytes)
        return {
            "final_url": resp.geturl(),
            "http_status": status,
            "headers": {k: headers.get(k) for k in HEADER_KEYS if k in headers},
            "bytes_read": len(data),
            "sha256": sha256_hex(data),
            "truncated": truncated,
            "accept_encoding": accept_encoding,
            # Internal: used for substring checks without refetching.
            "_body_sample": data,
        }


def fetch_range_segment(
    url: str,
    *,
    accept_encoding: str,
    timeout: float,
    user_agent: str,
    range_header: str,
    max_bytes: int,
):
    req = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": accept_encoding,
            "User-Agent": user_agent,
            "Range": range_header,
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", None)
        headers = {k.lower(): v for k, v in dict(resp.headers).items()}
        data, truncated = _read_limited(resp, max_bytes)
        return {
            "final_url": resp.geturl(),
            "http_status": status,
            "headers": {k: headers.get(k) for k in RANGE_HEADER_KEYS if k in headers},
            "bytes_read": len(data),
            "sha256": sha256_hex(data),
            "truncated": truncated,
            "accept_encoding": accept_encoding,
        }


def load_config(path: str):
    if yaml is None:
        raise SystemExit(
            "PyYAML is required to read monitors.yaml. Install with: pip install pyyaml"
        )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="YAML config file")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--user-agent", default=DEFAULT_UA)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    monitors = cfg.get("monitors") or []

    report = {
        "generated_at": utc_now_iso(),
        "config": {"path": args.config, "count": len(monitors)},
        "results": [],
    }

    for m in monitors:
        name = m.get("name") or m.get("url")
        url = m["url"]
        accept_encoding = m.get("accept_encoding") or "identity"
        max_bytes = int(m.get("max_bytes") or 200000)
        contains = m.get("contains")
        range_head_bytes = m.get("range_head_bytes")
        range_tail_bytes = m.get("range_tail_bytes")
        probe_type = "range" if (range_head_bytes or range_tail_bytes) else "full"

        entry = {"name": name, "url": url, "probe_type": probe_type}
        try:
            if probe_type == "full":
                fetched = fetch_full(
                    url,
                    accept_encoding=accept_encoding,
                    timeout=args.timeout,
                    max_bytes=max_bytes,
                    user_agent=args.user_agent,
                )
                entry.update(fetched)
                entry["body_sha256"] = entry.get("sha256")
                entry["body_bytes_read"] = entry.get("bytes_read")

                if contains is not None:
                    try:
                        contains_is_list = not isinstance(contains, str)
                        needles = [contains] if not contains_is_list else list(contains)
                        sample = entry.get("_body_sample") or b""
                        text = sample.decode("utf-8", errors="replace")
                        contains_results = []
                        for needle in needles:
                            ok = (needle in text)
                            contains_results.append({"needle": needle, "ok": ok})
                        entry["contains_results"] = contains_results
                        if contains_is_list:
                            entry["ok_contains_all"] = all(r["ok"] for r in contains_results)
                        # Back-compat: single-needle summary.
                        if len(needles) == 1:
                            entry["contains"] = contains_results[0]
                    except Exception as e:
                        entry["contains_results"] = [{"needle": contains, "ok": False, "error": str(e)}]
                status = entry.get("http_status")
                entry["ok"] = bool(status) and 200 <= status < 300
            else:
                # Range probe: head and/or tail.
                head_bytes = int(range_head_bytes) if range_head_bytes else None
                tail_bytes = int(range_tail_bytes) if range_tail_bytes else None
                statuses = []
                final_urls = []
                if head_bytes:
                    head_res = fetch_range_segment(
                        url,
                        accept_encoding=accept_encoding,
                        timeout=args.timeout,
                        user_agent=args.user_agent,
                        range_header=f"bytes=0-{head_bytes - 1}",
                        max_bytes=head_bytes,
                    )
                    entry.update(
                        {
                            "range_head_bytes": head_bytes,
                            "range_head_bytes_read": head_res.get("bytes_read"),
                            "range_head_sha256": head_res.get("sha256"),
                            "range_head_http_status": head_res.get("http_status"),
                            "range_head_final_url": head_res.get("final_url"),
                            "range_head_headers": head_res.get("headers"),
                            "range_head_truncated": head_res.get("truncated"),
                        }
                    )
                    statuses.append(head_res.get("http_status"))
                    final_urls.append(head_res.get("final_url"))
                if tail_bytes:
                    tail_res = fetch_range_segment(
                        url,
                        accept_encoding=accept_encoding,
                        timeout=args.timeout,
                        user_agent=args.user_agent,
                        range_header=f"bytes=-{tail_bytes}",
                        max_bytes=tail_bytes,
                    )
                    entry.update(
                        {
                            "range_tail_bytes": tail_bytes,
                            "range_tail_bytes_read": tail_res.get("bytes_read"),
                            "range_tail_sha256": tail_res.get("sha256"),
                            "range_tail_http_status": tail_res.get("http_status"),
                            "range_tail_final_url": tail_res.get("final_url"),
                            "range_tail_headers": tail_res.get("headers"),
                            "range_tail_truncated": tail_res.get("truncated"),
                        }
                    )
                    statuses.append(tail_res.get("http_status"))
                    final_urls.append(tail_res.get("final_url"))

                # Back-compat top-level hints.
                entry["http_status"] = statuses[0] if statuses else None
                entry["final_url"] = final_urls[0] if final_urls else None
                entry["accept_encoding"] = accept_encoding
                entry["ok"] = bool(statuses) and all((s and 200 <= s < 300) for s in statuses)

                if contains is not None:
                    entry["contains_results"] = [
                        {
                            "needle": contains,
                            "ok": False,
                            "error": "contains check requires full-body probe",
                        }
                    ]
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)

        entry.pop("_body_sample", None)

        report["results"].append(entry)

    out_path = args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
