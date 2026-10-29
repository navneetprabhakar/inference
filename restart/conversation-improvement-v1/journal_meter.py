"""Append-only reservation journal; identical counts, limits and checkpoint cursors."""
import json,os,hashlib,tempfile
from pathlib import Path
import campaign as c
s=c.s
class Writer:
    def __init__(self,path,data,suffix="test"):
        self.path=Path(path);self.prefix=self.path.with_name('ledger-prefix-'+suffix+'.json');self.journal=self.path.with_name('reservations-'+suffix+'.jsonl')
        assert not self.prefix.exists() and not self.journal.exists()
        s.save(self.prefix,data);self.count=len(data['reservations']);self.start_count=self.count
        self.handle=self.journal.open('x')
    def flush(self,data):
        for index,event in enumerate(data['reservations'][self.count:],start=self.count):
            self.handle.write(json.dumps(dict(index=index,event=event))+'\n')
        self.handle.flush();os.fsync(self.handle.fileno());self.count=len(data['reservations'])
        if 'active_segment' in data:
            compact={k:v for k,v in data.items() if k!='reservations'}
            compact['reservation_journal']=dict(prefix=str(self.prefix),journal=str(self.journal),count=self.count,prefix_count=self.start_count)
            s.save(self.path,compact)
        else:
            s.save(self.path,data);self.handle.close()
    def reconstructed(self):
        data=s.read(self.prefix)
        for line in self.journal.read_text().splitlines():
            row=json.loads(line);assert row['index']==len(data['reservations']);data['reservations'].append(row['event'])
        return data['reservations']
class Meter(c.Meter):
    def __init__(self,phase):
        self.writer=None
        super().__init__(phase)
        self.writer=Writer(self.path,self.data,phase)
    def flush(self):
        if self.writer is None:super().flush()
        else:self.writer.flush(self.data)
if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'ledger.json';d=dict(updates=1,positions=10,active_segment={'phase':'test'},reservations=[dict(updates=1,positions=10)])
        w=Writer(path,d)
        for i in range(3):
            event=dict(updates=0,positions=i+1);d['positions']+=i+1;d['reservations'].append(event);w.flush(d)
            assert w.reconstructed()==d['reservations'];assert s.read(path)['positions']==d['positions'];assert 'reservations' not in s.read(path)
        d.pop('active_segment');w.flush(d);assert s.read(path)==d
    print('PASS: prefix+journal reconstruct every reservation; compact counters and final full ledger agree.')
