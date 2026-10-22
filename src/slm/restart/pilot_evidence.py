"""Build pilot evidence from durable update completions and verified evaluations.

No hand-supplied throughput endpoints or NLL summaries are accepted. Supervised
active-time charges include evaluations/checkpointing and conservatively count
reserved ticks; interrupted/replayed work is never subtracted.
"""
import hashlib,json,math,sqlite3
from .monitor import StopRun
from . import update_step


class Measurements:
    def __init__(self,path,*,identity,schedule):
        self.schedule=schedule
        self.db=sqlite3.connect(path,isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS contract(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS completions(seq INTEGER PRIMARY KEY,reservation TEXT UNIQUE NOT NULL,
          step INTEGER NOT NULL,targets INTEGER NOT NULL,active REAL NOT NULL,ledger_pin TEXT NOT NULL);''')
        contract=json.dumps({'identity':identity,'schedule':schedule.sha256},sort_keys=True)
        self.db.execute('INSERT OR IGNORE INTO contract VALUES (1,?)',(contract,))
        if self.db.execute('SELECT value FROM contract').fetchone()[0]!=contract:
            self.db.close();raise ValueError('Changed pilot measurement contract')

    def completed(self,update,*,reservation,ledger,time_budget):
        if update!=self.schedule.updates[update.step-1]:raise ValueError('Unbound timing update')
        row=ledger.db.execute('SELECT targets,completed FROM reservations WHERE id=?',(reservation,)).fetchone()
        if row!=(update.targets,1):raise ValueError('Measurement requires completed charged update')
        if time_budget.terminal() is not None:raise ValueError('Terminal supervised clock')
        active=time_budget.charged()
        last=self.db.execute('SELECT active FROM completions ORDER BY seq DESC LIMIT 1').fetchone()
        if not 0<active<=time_budget.cap or last and active<last[0]:raise ValueError('Invalid/reversed active clock')
        self.db.execute('INSERT INTO completions(reservation,step,targets,active,ledger_pin) VALUES (?,?,?,?,?)',
            (reservation,update.step,update.cumulative_targets,active,ledger.snapshot()['digest']))

    def throughput(self):
        rows=self.db.execute('SELECT targets,active FROM completions ORDER BY seq').fetchall()
        eligible=[row for row in rows if row[0]>=250000]
        if not eligible or rows[-1][0]!=2000000:raise ValueError('Missing post-warmup pilot measurement')
        start,end=eligible[0],rows[-1]
        return dict(start_targets=start[0],end_targets=end[0],start_active_seconds=start[1],end_active_seconds=end[1])

    def close(self):self.db.close()


def execute_measured(update,*,measurements,time_budget,**kwargs):
    result=update_step.execute(update,**kwargs)
    try:measurements.completed(update,reservation=kwargs['reservation_id'],ledger=kwargs['ledger'],time_budget=time_budget)
    except BaseException as error:
        kwargs['monitor'].terminal='Pilot measurement failed: '+str(error)
        raise
    return result


def collect(*,barrier,measurements,time_budget,elapsed_seconds,target_cap,dev_verify,full_verify):
    step=barrier.position()
    if step==0 or barrier.schedule.updates[step-1].cumulative_targets!=2000000:
        raise ValueError('Pilot evidence requires exact 2M boundary')
    if barrier.pending():raise ValueError('Pilot diagnostics remain pending')
    dev=[];full=None;evidence_pins=[]
    for event,raw,pin in barrier.db.execute('SELECT event,raw,sha256 FROM evidence ORDER BY step,event'):
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Changed accepted pilot evidence')
        p=json.loads(raw);context=p['context'];targets=context['targets']
        if targets>2000000:raise ValueError('Continuation occurred before pilot decision')
        if event=='dev_loss_checkpoint':
            metrics=dev_verify(raw,context)
            dev.append({'targets':targets,'evaluated_targets':p['metrics']['targets'],'nll':metrics['nll']})
        elif event=='full_development_diagnostics':
            if targets!=2000000 or full is not None:raise ValueError('Unexpected pilot full diagnostic')
            metrics=full_verify(raw,context)
            full={'grammar_items':len(p['grammar']['outputs']),'grounded_items':len(p['grounded']['outputs']),
                  'narrative_items':len(p['narratives']['outputs']),'smoke_items':20,'evaluation_errors':0,
                  'degenerate_smoke_items':metrics['degenerate_outputs']}
        evidence_pins.append(pin)
    if full is None:raise ValueError('Missing verified pilot diagnostics')
    evidence={'targets':2000000,'dev_records':dev,'diagnostics':full,'throughput':measurements.throughput(),
              'active_seconds':time_budget.charged(),'elapsed_seconds':elapsed_seconds,'target_cap':target_cap,
              'terminal_reason':time_budget.terminal()}
    return evidence,{'accepted_evidence_sha256':evidence_pins,
                     'measurement_rows':measurements.db.execute('SELECT count(*) FROM completions').fetchone()[0]}
