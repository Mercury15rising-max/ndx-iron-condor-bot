"""One dated paper-only SPXW quote evaluation. No orders, fills or scheduler."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from paper_strategy_lab import compare
from paper_ledger import PaperLedger


def run(snapshot, ledger):
    now=datetime.now(timezone.utc)
    captured=datetime.fromisoformat(snapshot['as_of'].replace('Z','+00:00'))
    if captured.tzinfo is None or not -2 <= (now-captured).total_seconds() <= 30:
        raise ValueError('Snapshot must be freshly collected')
    rows=compare(snapshot['quotes'],now,overnight_test=True)
    return [dict(ledger.gate(r,now.isoformat()),mode='overnight_research_only',filled=False,
                 live_execution_enabled=False) for r in rows]

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('snapshot');p.add_argument('--ledger',required=True);p.add_argument('--journal',required=True)
    a=p.parse_args()
    rows=run(json.loads(Path(a.snapshot).read_text()),PaperLedger(a.ledger))
    with open(a.journal,'a') as f:
        for r in rows:f.write(json.dumps(r,allow_nan=False)+'\n')
    print(json.dumps({'evaluations':len(rows),'candidates':sum(r['status']=='research_candidate' for r in rows),'fills':0}))
