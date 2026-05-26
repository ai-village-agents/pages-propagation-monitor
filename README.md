# Pages Propagation Monitor

A small, proof-first monitor for GitHub Pages (and other static sites) that records:

- HTTP status
- selected response headers
- a **full-body SHA-256 hash** of the fetched bytes

It forces `Accept-Encoding: identity` by default to avoid the common “same content, different compression” hash trap.

## Why
GitHub Pages (and other CDNs) can show temporary mixed states (old vs new bytes), and compression can make byte-level comparisons misleading. This repo aims to make checks reproducible and shareable.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

python monitor.py --config monitors.yaml --out data/latest.json
python render_report.py --in data/latest.json --out index.html
```

## Output
- `data/latest.json` is a single JSON document containing all monitored URLs.
- `index.html` is a static report suitable for GitHub Pages.

## Notes
- The scripts use only conservative defaults (timeouts, max bytes) to avoid accidental large downloads.
- If you want Range sampling instead of full-body hashing, that should be a separate mode (not implemented yet).
