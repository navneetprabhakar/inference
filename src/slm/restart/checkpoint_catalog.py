"""Durable complete-checkpoint inventory, verified dev selection and retention.

Stores every historical manifest/evaluation digest even after weight pruning.
Only owned, verified complete checkpoints may be registered or retired.
"""
import hashlib,json,math,os,shutil,sqlite3
from pathlib import Path
from . import checkpoint_binding,state


class Catalog:
    def __init__(self,db_path,*,root,identity,expected,shapes,schedule,ledger):
        self.root=Path(root).absolute()
        if self.root.resolve(strict=True)!=self.root:raise ValueError('Redirected checkpoint root')
        self.args=dict(identity=identity,expected=expected,shapes=shapes,schedule=schedule,ledger=ledger)
        self.db=sqlite3.connect(db_path,isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS contract(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS checkpoints(seq INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,pin TEXT NOT NULL,
          step INTEGER NOT NULL,targets INTEGER NOT NULL,nll REAL,evidence_pin TEXT,status TEXT NOT NULL);''')
        contract=json.dumps(dict(root=str(self.root),identity=identity,expected=expected,shapes=shapes,schedule=schedule.sha256),sort_keys=True)
        self.db.execute('INSERT OR IGNORE INTO contract VALUES (1,?)',(contract,))
        if self.db.execute('SELECT value FROM contract').fetchone()[0]!=contract:
            self.db.close();raise ValueError('Changed checkpoint catalog contract')

    def _path(self,name):
        p=self.root/name
        if Path(name).name!=name or name.startswith('.') or p.resolve(strict=True)!=p:
            raise ValueError('Unowned checkpoint path')
        return p

    def register(self,name):
        path=self._path(name)
        restored=checkpoint_binding.restore(path,**self.args)
        meta=restored['metadata'];pin=state.digest(path/'manifest.json')
        self.db.execute('INSERT INTO checkpoints(name,pin,step,targets,status) VALUES (?,?,?,?,?)',
                        (name,pin,meta['step'],meta['targets'],'retained'))
        return pin

    def score(self,name,barrier):
        # A verified plateau may commit its triggering dev score. Other terminal
        # failures cannot acquire a new best checkpoint.
        if not hasattr(barrier,'clean_stop') or barrier.clean_stop() is None:barrier.position()
        row=self.db.execute('SELECT pin,step,targets,nll,status FROM checkpoints WHERE name=?',(name,)).fetchone()
        if row is None or row[4]!='retained':raise ValueError('Unknown/unretained checkpoint')
        pin,step,targets,previous,_=row
        if state.digest(self._path(name)/'manifest.json')!=pin:raise ValueError('Changed checkpoint')
        found=barrier.db.execute("SELECT raw,sha256 FROM evidence WHERE step=? AND event='dev_loss_checkpoint'",(step,)).fetchone()
        if found is None or hashlib.sha256(found[0]).hexdigest()!=found[1]:raise ValueError('Missing or changed accepted dev evidence')
        payload=json.loads(found[0]);context=payload['context']
        if (context['checkpoint_sha256']!=pin or context['identity']!=self.args['identity']
                or context['schedule_sha256']!=self.args['schedule'].sha256 or context['targets']!=targets):
            raise ValueError('Development evidence belongs to another checkpoint')
        value=payload['metrics']['nll']
        if type(value) not in (int,float) or not math.isfinite(value) or value<=0:raise ValueError('Invalid accepted dev loss')
        if previous is not None:
            prior_pin=self.db.execute('SELECT evidence_pin FROM checkpoints WHERE name=?',(name,)).fetchone()[0]
            if previous!=value or prior_pin!=found[1]:raise ValueError('Changed checkpoint score')
            return
        self.db.execute('UPDATE checkpoints SET nll=?,evidence_pin=? WHERE name=?',(value,found[1],name))

    def reconcile_scores(self,barrier):
        """Finish interrupted score bookkeeping without changing accepted evidence."""
        barrier.position()
        for step,raw,pin in barrier.db.execute("SELECT step,raw,sha256 FROM evidence WHERE event='dev_loss_checkpoint'"):
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Changed accepted development evidence')
            context=json.loads(raw)['context']
            rows=self.db.execute("SELECT name,nll,status FROM checkpoints WHERE pin=? AND step=?",(context['checkpoint_sha256'],step)).fetchall()
            if len(rows)!=1:raise ValueError('Missing or ambiguous score publication')
            name,nll,status=rows[0]
            if nll is None:
                if status!='retained':raise ValueError('Unscored accepted checkpoint was lost')
                self.score(name,barrier)

    def evaluation_checkpoint(self,barrier):
        """Recover the exact checkpoint for a partly committed diagnostic boundary.

        Acceptance and catalog scoring use separate durable stores. Reconcile a
        committed dev score here if interruption occurred between those writes.
        Never replace accepted evidence or choose different weights.
        """
        step=barrier.position()
        evidence=barrier.db.execute('SELECT event,raw,sha256 FROM evidence WHERE step=?',(step,)).fetchall()
        if not evidence:return None
        pins=set()
        for event,raw,pin in evidence:
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Changed accepted boundary evidence')
            context=json.loads(raw)['context']
            if (context['identity']!=self.args['identity'] or context['schedule_sha256']!=self.args['schedule'].sha256
                    or context['step']!=step or context['event']!=event):raise ValueError('Unbound boundary evidence')
            pins.add(context['checkpoint_sha256'])
        if len(pins)!=1:raise ValueError('Ambiguous boundary checkpoint')
        rows=self.db.execute("SELECT name,pin FROM checkpoints WHERE pin=? AND step=? AND status='retained'",(pins.pop(),step)).fetchall()
        if len(rows)!=1:raise ValueError('Accepted boundary checkpoint unavailable')
        name,pin=rows[0];path=self._path(name)
        if state.digest(path/'manifest.json')!=pin:raise ValueError('Changed boundary checkpoint')
        restored=checkpoint_binding.restore(path,**self.args)
        if any(restored['charged_work_after_checkpoint'].values()):raise ValueError('Boundary checkpoint behind charged work')
        if any(event=='dev_loss_checkpoint' for event,_,_ in evidence):self.score(name,barrier)
        return path

    def keep(self):
        recent=[r[0] for r in self.db.execute("SELECT name FROM checkpoints WHERE status='retained' ORDER BY seq DESC LIMIT 2")]
        best=self.db.execute("SELECT name FROM checkpoints WHERE nll IS NOT NULL ORDER BY nll,seq LIMIT 1").fetchone()
        if best:
            if self.db.execute('SELECT status FROM checkpoints WHERE name=?',best).fetchone()[0]!='retained':
                raise ValueError('Best checkpoint was lost')
            recent.append(best[0])
        return set(recent)

    def prune(self):
        keep=self.keep()
        for name,pin,status in self.db.execute("SELECT name,pin,status FROM checkpoints WHERE status!='pruned' ORDER BY seq").fetchall():
            if name in keep:continue
            path=self.root/name
            retired=self.root/('.retired-'+hashlib.sha256((name+pin).encode()).hexdigest())
            if status=='retained':
                path=self._path(name)
                if state.digest(path/'manifest.json')!=pin:raise ValueError('Refuse pruning changed checkpoint')
                checkpoint_binding.restore(path,**self.args)
                self.db.execute("UPDATE checkpoints SET status='retiring' WHERE name=?",(name,))
            if path.exists():
                if retired.exists():raise ValueError('Ambiguous retirement state')
                if self._path(name)!=path or state.digest(path/'manifest.json')!=pin:raise ValueError('Changed retirement target')
                os.rename(path,retired)
                fd=os.open(self.root,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)
            if retired.exists():
                if retired.is_symlink() or not retired.is_dir():raise ValueError('Redirected retirement directory')
                shutil.rmtree(retired)
            self.db.execute("UPDATE checkpoints SET status='pruned' WHERE name=?",(name,))
        return self.keep()

    def best(self):
        row=self.db.execute("SELECT name,pin,nll FROM checkpoints WHERE status='retained' AND nll IS NOT NULL ORDER BY nll,seq LIMIT 1").fetchone()
        if row is None:raise ValueError('No evaluated checkpoint')
        path=self._path(row[0])
        if state.digest(path/'manifest.json')!=row[1]:raise ValueError('Changed best checkpoint')
        checkpoint_binding.restore(path,**self.args)
        return {'path':str(path),'manifest_sha256':row[1],'dev_nll':row[2]}

    def close(self):self.db.close()
