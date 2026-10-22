"""Retained training measurements and static plots; no model operations."""
import hashlib,json,math,os
from pathlib import Path
from .final_state import readonly,digest
from .evaluation_snapshot import _file
from .supervisor import verify_resource_history


def histories(candidate,*,identity,schedule_sha256):
    candidate=Path(candidate).absolute();pins={};updates=[]
    db=readonly(candidate/'measurements.sqlite',immutable=False)
    ledger=readonly(candidate/'exposures.sqlite',immutable=False)
    try:
        if json.loads(db.execute('SELECT value FROM contract WHERE id=1').fetchone()[0])!=dict(identity=identity,schedule=schedule_sha256):
            raise ValueError('Unbound delivery measurements')
        reservations={r[0]:(r[1],r[2]) for r in ledger.execute('SELECT id,targets,completed FROM reservations')}
        measured=db.execute('SELECT seq,reservation,step,targets,active,ledger_pin FROM completions ORDER BY seq').fetchall()
        last_active=-1
        for seq,reservation,step,targets,active,ledger_pin in measured:
            if reservation not in reservations or reservations[reservation][1]!=1 or active<last_active:
                raise ValueError('Delivery timing differs from charged work')
            last_active=active
            row=dict(sequence=seq,reservation=reservation,step=step,cumulative_targets=targets,charged_active_seconds=active,ledger_sha256=ledger_pin)
            path=candidate/(reservation+'-metrics.json')
            if path.exists():
                path=_file(candidate,path.name);metric=json.loads(path.read_bytes())
                if set(metric)!={'loss','gradient_norm','update_ratio','microbatches','supervised_targets'}:
                    raise ValueError('Invalid raw update measurement')
                if any(type(metric[k]) not in (int,float) or not math.isfinite(metric[k]) or metric[k]<0 for k in ('loss','gradient_norm','update_ratio')):
                    raise ValueError('Invalid raw numerical history')
                if type(metric['microbatches']) is not int or metric['microbatches']<1 or type(metric['supervised_targets']) is not int or metric['supervised_targets']!=reservations[reservation][0]:
                    raise ValueError('Raw targets differ from ledger')
                row['metrics']=metric;pins[path.name]=digest(path)
            else:
                row['metrics']=None;row['missing_reason']='No persisted metrics; possible interruption after completion. No values reconstructed.'
            updates.append(row)
        if set(p.name for p in candidate.glob('work-*-metrics.json'))-{r[1]+'-metrics.json' for r in measured}:
            raise ValueError('Unbound extra update metrics')
        charged=dict(updates_reserved=len(reservations),targets_reserved=sum(r[0] for r in reservations.values()),updates_completed=sum(r[1] for r in reservations.values()))
    finally:db.close();ledger.close()
    resources={}
    for phase in ('pilot','pilot-recovery','continuation','continuation-recovery'):
        path=candidate/(phase+'-supervisor.json')
        if path.exists():resources[phase]=verify_resource_history(path);pins[path.name]=digest(path)
    path=candidate/'final-run-v1/supervisor.json'
    if path.exists():resources['final']=verify_resource_history(path);pins['final-run-v1/supervisor.json']=digest(path)
    return dict(updates=updates,resources=resources,charged_work=charged,source_sha256=pins,
        missing_metric_records=sum(r['metrics'] is None for r in updates),
        note='Reservation sequence preserves replay and charges. Cumulative schedule targets may repeat after recovery; missing observations are explicit.')


def build(candidate,output,*,identity,schedule_sha256,heartbeat):
    output=Path(output).absolute();root=output/'delivery';root.mkdir()
    data=histories(candidate,identity=identity,schedule_sha256=schedule_sha256);heartbeat()
    raw=(json.dumps(data,indent=2,allow_nan=False)+'\n').encode();(root/'histories.json').write_bytes(raw)
    # Plotting is isolated from neural math and cannot change metrics or verdicts.
    os.environ['MPLCONFIGDIR']=str(output/'.matplotlib')
    import matplotlib
    if matplotlib.__version__!='3.10.7':raise ValueError('Unpinned plotting version')
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(9,8),layout='constrained',sharex=True)
    for ax,key,label in zip(axes,('loss','gradient_norm','update_ratio'),('Training NLL','Pre-clip gradient norm','Parameter update ratio')):
        ax.plot([r['sequence'] for r in data['updates']],[r['metrics'][key] if r['metrics'] is not None else float('nan') for r in data['updates']],linewidth=.8)
        ax.set_ylabel(label);ax.grid(alpha=.25)
    axes[-1].set_xlabel('Completed-work sequence (replays retained)');fig.suptitle('Observed update history — no smoothing or reconstructed values')
    fig.savefig(root/'updates.png',dpi=150);plt.close(fig);heartbeat()
    fig,axes=plt.subplots(3,1,figsize=(9,8),layout='constrained',sharex=True)
    for phase,rows in data['resources'].items():
        samples=rows[1:-1]
        for ax,key,label in zip(axes,('rss_gib','swap_growth_mib','free_disk_gib'),('Process-group RSS (GiB)','Swap growth (MiB)','Free disk (GiB)')):
            ax.plot([r['charged_active_seconds']/3600 for r in samples],[r['measurement'][key] for r in samples],label=phase,linewidth=.8)
            ax.set_ylabel(label);ax.grid(alpha=.25)
    axes[-1].set_xlabel('Cumulative charged active hours')
    if data['resources']:axes[0].legend(fontsize=7)
    fig.suptitle('Observed resource samples — between-sample peaks unknown')
    fig.savefig(root/'resources.png',dpi=150);plt.close(fig);heartbeat()
    manifest=dict(schema=1,identity=identity,files={p.name:digest(p) for p in sorted(root.iterdir()) if p.is_file()},
        charged_work=data['charged_work'],missing_metric_records=data['missing_metric_records'],plotting=dict(library='matplotlib',version=matplotlib.__version__),
        scope='Raw histories and static plots; evaluation outputs, baseline comparisons and checkpoint references remain in the research report')
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return dict(directory=str(root),manifest_sha256=digest(root/'manifest.json'),**manifest)


def verify(output,record,*,identity):
    root=Path(output).absolute()/'delivery'
    if record['directory']!=str(root) or root.resolve(strict=True)!=root:raise ValueError('Unowned delivery bundle')
    path=_file(root,'manifest.json')
    if digest(path)!=record['manifest_sha256']:raise ValueError('Changed delivery manifest')
    manifest=json.loads(path.read_bytes())
    if manifest['identity']!=identity or any(record.get(k)!=v for k,v in manifest.items()):raise ValueError('Unbound delivery record')
    if set(p.name for p in root.iterdir())!=set(manifest['files'])|{'manifest.json'}:raise ValueError('Changed delivery inventory')
    for name,pin in manifest['files'].items():
        if digest(_file(root,name))!=pin:raise ValueError('Changed delivery artifact')
    return manifest
