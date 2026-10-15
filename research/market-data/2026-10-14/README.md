# October 14, 2026 historical market research

The original uploaded dataset is attached to this repository as `strategy-data-2026-10-14.zip`. Its JSON member is byte-for-byte identical to the separately uploaded JSON. See `manifest.json` for SHA-256 checksums and provenance.

This is a research collection, not a trading archive, paper ledger, forward snapshot, or approved entry bundle. Adding it does not feed the running worker or authorize any trades. Do not copy it over existing trading archives or reinterpret its timestamps as current. No strategy settings or runtime behavior are changed.

## Read without modifying the archive

From the repository root:

```python
import hashlib
import json
import zipfile
from pathlib import Path

root = Path("research/market-data/2026-10-14")
manifest = json.loads((root / "manifest.json").read_text())
archive = root / manifest["archive"]["path"]
assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archive"]["sha256"]
with zipfile.ZipFile(archive) as z:
    raw = z.read(manifest["json"]["member"])
assert hashlib.sha256(raw).hexdigest() == manifest["json"]["sha256"]
dataset = json.loads(raw)
print(dataset["date"], dataset["completed_at"])
```

## Coverage and limitations

- 14 context-only equity symbols, 1,092 five-minute candles (78 per symbol), and 6,770 option quotes.
- Candles retain provider left-edge `begins_at` timestamps. A five-minute bar completes five minutes after that label; do not use its close before completion.
- Only one full session is present. EMA signals require at least 106 completed candles; the validated paper pipeline requires three complete sessions. VWAP additionally requires explicit trade-volume provenance.
- Sequential option batches are not a simultaneous executable snapshot. All option quotes exceed the paper engine's 60-second freshness threshold at their original batch receipt times. Collection receipts are outside the normal 10:00–14:30 New York entry window.
- 653 quotes lack delta, 1,403 fail positive uncrossed bid/ask or minimum-size checks, and 6,716 lack an official prior close. Quality categories can overlap.
- The raw `research_collection_v1` schema is not the pipeline's version-1 observed bundle schema. Do not bypass validation, manufacture prior sessions, forward-fill missing deltas, or refresh old timestamps to make it pass.

## Setup review

No setup qualifies under the inspected review-branch rules. QQQ EMA transitions computed without warmup are illustrative only. The fixed earliest-expiry NDXP condor cannot rank the full universe with missing deltas; among known deltas its October 15 short call is 30320C and the exact required 30345C wing is absent. October 16 is not a permitted fallback; its diagnostic 29300P/29325P/30450C/30475C condor yields a $700 debit at bid/ask sides, not a credit. Equity symbols remain context-only.

These observations establish neither historical fills nor P&L. Preserve original timestamps for all further research.
