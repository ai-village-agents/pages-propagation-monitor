# Deploy proof checklist (Pages propagation monitor)

When GitHub Pages is enabled but serving 404 or mixed bytes, collect a proof bundle:

```bash
REPO=ai-village-agents/pages-propagation-monitor
python - <<'PY'
import json,subprocess,sys,hashlib
from urllib.request import Request,urlopen

def sh(cmd):
    return subprocess.check_output(cmd, shell=True, text=True)

# 1) Pages config
print(sh("gh api repos/%s/pages --jq '{status,build_type,source,html_url}'" % "ai-village-agents/pages-propagation-monitor"))

# 2) Latest build (may 404)
try:
    print(sh("gh api repos/%s/pages/builds/latest --jq '{status,commit,created_at,updated_at}'" % "ai-village-agents/pages-propagation-monitor"))
except Exception as e:
    print("latest_build_error", e)

# 3) Live fetch (identity encoding)
url='https://ai-village-agents.github.io/pages-propagation-monitor/'
req=Request(url, headers={'Accept-Encoding':'identity'})
with urlopen(req, timeout=20) as r:
    data=r.read(1000000)
print('http_status', getattr(r,'status',None))
print('bytes', len(data))
print('sha256', hashlib.sha256(data).hexdigest())
print('contains', 'Pages Propagation Monitor' in data.decode('utf-8','replace'))
PY
```

Store JSON in `data/` and (optionally) commit it.
