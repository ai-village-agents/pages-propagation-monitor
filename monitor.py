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


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_hex(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def fetch(url: str, *, accept_encoding: str, timeout: float, max_bytes: int, user_agent: str):
    req = urllib.request.Request(url, headers={
        "Accept-Encoding": accept_encoding,
        "User-Agent": user_agent,
    })

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", None)
        headers = {k.lower(): v for k, v in dict(resp.headers).items()}
        data = resp.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        return {
            "final_url": resp.geturl(),
            "http_status": status,
            "headers": {k: headers.get(k) for k in [
                "cache-control",
                "content-type",
                "content-encoding",
                "etag",
                "last-modified",
                "age",
                "via",
                "x-served-by",
            ] if k in headers},
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

        entry = {"name": name, "url": url}
        try:
            fetched = fetch(
                url,
                accept_encoding=accept_encoding,
                timeout=args.timeout,
                max_bytes=max_bytes,
                user_agent=args.user_agent,
            )
            entry.update(fetched)

            if contains is not None:
                # best-effort: decode with replacement
                try:
                    with urllib.request.urlopen(
                        urllib.request.Request(url, headers={"Accept-Encoding": accept_encoding, "User-Agent": args.user_agent}),
                        timeout=args.timeout,
                    ) as resp:
                        data = resp.read(max_bytes)
                    text = data.decode("utf-8", errors="replace")
                    entry["contains"] = {"needle": contains, "ok": (contains in text)}
                except Exception as e:
                    entry["contains"] = {"needle": contains, "ok": False, "error": str(e)}

            entry["ok"] = (entry.get("http_status") == 200)
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)

        report["results"].append(entry)

    out_path = args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
