"""Read-only status; never imports an engine or starts GPU work."""
import json,time
from pathlib import Path
root=Path(__file__).resolve().parent
if (root/'report.json').exists():print((root/'report.json').read_text());raise SystemExit
clock=json.loads((root/'clock.json').read_text())
out={'total_minutes':round((time.time()-clock['start_epoch'])/60,1)}
if (root/'jobs.json').exists():
    job=json.loads((root/'jobs.json').read_text())[-1];out['job']=job['name'];out['job_minutes']=round((time.time()-job['start_epoch'])/60,1)
    p=root/job['name']/'progress.json'
    if p.exists():
        rows=list(map(json.loads,(p.parent/'updates.jsonl').read_text().splitlines()));recent=rows[-5:]
        out.update(updates=len(rows),recent_tps=round(sum(r['targets'] for r in recent)/sum(r['seconds'] for r in recent)),GPU_peak_GiB=round(max(r['peak_active_or_driver_bytes'] for r in rows)/1024**3,2))
    p=root/job['name']/'acceptance-progress.json'
    if p.exists():out['numerical']={k:v['status'] for k,v in json.loads(p.read_text()).items()}
p=root/'resources.jsonl'
if p.exists():
    rows=list(map(json.loads,p.read_text().splitlines()));out.update(RSS_peak_GiB=round(max(r['RSS_bytes'] for r in rows)/1024**3,2),swap_growth_MiB=round(max(r['global_swap_growth_bytes'] for r in rows)/1024**2,1))
print(json.dumps(out))
