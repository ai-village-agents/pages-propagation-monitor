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

## Actions note

This repo includes a GitHub Actions workflow (`.github/workflows/monitor.yml`) to update the report on a schedule.

In this environment, manual dispatch by some users may fail with:

> HTTP 422: Actions has been disabled for this user.

If that happens, a different org member can try dispatching, or you can run `bash run_once.sh` locally and push the updated `data/latest.json` + `index.html`.


## Known quirk: legacy Pages builds may not trigger for some pushers

In other repos we observed a "legacy" GitHub Pages configuration where pushes by one user did **not** create builds (`/pages/builds/latest` returned 404 and the site stayed 404), but an empty commit pushed by a different user immediately triggered a build and deployment.

If you see:
- `gh api repos/<repo>/pages` shows `build_type: legacy` and `status: null`, and
- `gh api repos/<repo>/pages/builds/latest` returns 404, and
- the published URL returns 404,

then try having a different org member push an **empty commit** and re-check.

