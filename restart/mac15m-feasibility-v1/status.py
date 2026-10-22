"""Read-only live summary; never starts or modifies a training process."""
import json
from pathlib import Path

root=Path(__file__).resolve().parent
run=root/'run'
if (root/'report.json').exists():
    print((root/'report.json').read_text())
else:
    rows=[json.loads(s) for s in (run/'updates.jsonl').read_text().splitlines()]
    resources=[json.loads(s) for s in (run/'resources.jsonl').read_text().splitlines()]
    last=resources[-1];recent=rows[-5:]
    print(json.dumps(dict(minutes=round(last['elapsed']/60,1),updates=len(rows),
        recent_training_tokens_per_second=round(sum(x['targets'] for x in recent)/sum(x['seconds'] for x in recent)),
        targets=rows[-1]['total_targets'],last_loss=round(rows[-1]['loss'],3),
        driver_GiB=round(max(x['mps_driver_bytes'] for x in rows)/1024**3,2),
        peak_RSS_GiB=round(max(x['rss_bytes'] for x in resources)/1024**3,2),
        swap_growth_MiB=round(max(x['swap_growth_bytes'] for x in resources)/1024**2,1))))
