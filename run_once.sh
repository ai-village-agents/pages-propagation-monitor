#!/usr/bin/env bash
set -euo pipefail
python monitor.py --config monitors.yaml --out data/latest.json
python render_report.py --in data/latest.json --out index.html
