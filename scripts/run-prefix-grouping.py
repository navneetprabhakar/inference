"""Bounded immutable full-feature prefix join and terminal streaming audit."""
# Creator: Navneet Prabhakar
import json,os,signal,sqlite3,struct,subprocess,sys,time,shutil,resource
from pathlib import Path
from slm.data.prefix_near import PrefixStore,prefix_length
from slm.data.curation import shingles
from slm.data.prose_screen import word_key
from slm.data.schema import digest
from slm.data.stream_hash import sha

def save(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def fields(text):
    return {k:v for k,v in json.loads(text)['texts'].items() if len(word_key(v))>=16 and len(word_key(v).split())>=4}
def check(plan):
    for p,h in plan['inputs'].items():
        if sha(p)!=h:raise ValueError('Frozen input differs: '+p)
def worker(plan_path):
    plan=json.loads(Path(plan_path).read_text());check(plan);out=Path(plan['output']);t=time.monotonic()
    source=sqlite3.connect('file:'+str(Path(plan['source']).resolve())+'?mode=ro',uri=True)
    counts={};raw=Path(plan['ordering']).read_bytes()
    for i in range(0,len(raw),36):counts[raw[i:i+32]]=struct.unpack('<I',raw[i+32:i+36])[0]
    s=PrefixStore(out/'index',counts,max_facets=plan['max_facets'],max_features=plan['max_features'],max_pairs=plan['max_pairs'],max_db_bytes=plan['max_database_bytes'],cache_kib=262144)
    selected=None if plan['selection'] is None else set(plan['selection']);n=refs=0
    for sid,data in source.execute('SELECT sid,data FROM records ORDER BY sid'):
        if selected is not None and sid not in selected:continue
        for name,text in fields(data).items():s.insert_facet(sid,name,text);refs+=1
        n+=1
        if n%2048==0:
            s.commit();r=dict(source_records=n,facets=s.facets,features=s.features,prefixes=s.postings,candidates=s.pairs,elapsed=time.monotonic()-t)
            save(out/'progress.json',r);print(json.dumps(r),flush=True)
    s.commit();build=time.monotonic()-t
    save(out/'build.json',dict(source_records=n,references=refs,facets=s.facets,features=s.features,prefixes=s.postings,candidates=s.pairs,build_seconds=build))
    s.close();db=sqlite3.connect('file:'+str((out/'index/near.sqlite').resolve())+'?mode=ro',uri=True)
    db.execute('PRAGMA temp_store=FILE');db.execute('PRAGMA cache_size=-131072')
    # Complete source mapping and full-feature/prefix reconstruction, one sorted prefix stream.
    mappings=0
    for sid,data in source.execute('SELECT sid,data FROM records ORDER BY sid'):
        if selected is not None and sid not in selected:continue
        actual=dict(db.execute('SELECT f.facet,r.data FROM facet_sources f JOIN records r ON r.sid=f.sid WHERE f.source_sid=?',(sid,)))
        expected=fields(data)
        if actual!=expected:raise ValueError('Source facet mapping differs')
        mappings+=len(expected)
    if mappings!=refs or db.execute('SELECT count(*) FROM facet_sources').fetchone()[0]!=refs:raise ValueError('Unexpected mapping')
    stream=iter(db.execute('SELECT sid,feat FROM prefixes ORDER BY sid,feat'));pending=next(stream,None);full=prefixes=0
    with (out/'index/full-shingles.bin').open('rb') as f:
        for sid,text,fingerprint,nf,offset,k in db.execute('SELECT sid,data,exact,n,offset,prefix_length FROM records ORDER BY sid'):
            values=shingles(text);hashes=sorted(bytes.fromhex(digest(v)) for v in values)
            if digest(text)!=fingerprint or offset!=full*32 or nf!=len(hashes) or f.read(nf*32)!=b''.join(hashes):raise ValueError('Full-feature reference differs')
            expected=set(sorted(hashes,key=lambda h:(counts.get(h,0),h))[:prefix_length(nf)]);actual=set()
            while pending is not None and pending[0]==sid:actual.add(pending[1]);pending=next(stream,None)
            if actual!=expected or k!=len(actual):raise ValueError('Prefix differs')
            full+=nf;prefixes+=k
        if f.read(1) or pending is not None:raise ValueError('Unexpected feature tail')
    pairs=0
    for a,b,ta,tb in db.execute('SELECT p.a,p.b,a.data,b.data FROM near_pairs p JOIN records a ON a.sid=p.a JOIN records b ON b.sid=p.b'):
        x,y=shingles(ta),shingles(tb)
        if a>=b or 20*len(x&y)<17*len(x|y):raise ValueError('False near edge')
        pairs+=1
    # Independent prefix/length self-join counts every proposed pair once.
    candidates=db.execute('''SELECT count(*) FROM (SELECT DISTINCT p.sid,q.sid FROM prefixes p JOIN prefixes q ON p.feat=q.feat AND p.sid<q.sid JOIN records a ON a.sid=p.sid JOIN records b ON b.sid=q.sid WHERE 20*a.n>=17*b.n AND 17*a.n<=20*b.n)''').fetchone()[0]
    if candidates!=s.pairs or full!=s.features or prefixes!=s.postings:raise ValueError('Full retrieval/accounting differs')
    db.close();source.close();check(plan)
    r=dict(creator='Navneet Prabhakar',complete=True,kind='exact-prefix-grouping-v1',plan_sha256=sha(plan_path),source_records=n,source_facet_references=refs,unique_facets=s.facets,full_features=full,prefix_postings=prefixes,candidate_pairs=candidates,qualifying_pairs=pairs,build_seconds=build,audit_seconds=time.monotonic()-t-build,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),full_population=selected is None,training_approved=False,model_updates=0,teacher_calls=0,files={str(p.relative_to(out)):sha(p) for p in [out/'index/near.sqlite',out/'index/full-shingles.bin']})
    save(out/'report.json',r);print(json.dumps(r),flush=True)
def main():
    p=sys.argv[1]
    if '--worker' in sys.argv:worker(p);return
    plan=json.loads(Path(p).read_text());check(plan);out=Path(plan['output'])
    if out.exists():raise FileExistsError('Retain previous attempt')
    out.mkdir();shutil.copyfile(p,out/'plan.json');shutil.copyfile(__file__,out/'executed-runner.py');shutil.copyfile('src/slm/data/prefix_near.py',out/'executed-prefix-near.py')
    child=subprocess.Popen([sys.executable,__file__,p,'--worker'],start_new_session=True);t=time.monotonic()
    save(out/'process.json',dict(parent=os.getpid(),child=child.pid,wall_seconds=plan['wall_seconds']))
    try:
        while child.poll() is None:
            if time.monotonic()-t>plan['wall_seconds']:raise TimeoutError('Finite join wall limit')
            if shutil.disk_usage(out).free<plan['minimum_free_bytes']:raise ValueError('Free disk reserve')
            if sum(f.stat().st_size for f in out.rglob('*') if f.is_file())>plan['max_work_bytes']:raise ValueError('Retained work cap')
            time.sleep(2)
        if child.returncode:raise RuntimeError('Join worker failed')
        save(out/'supervisor-terminal.json',dict(complete=True,returncode=0))
    except BaseException as e:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
        save(out/'supervisor-terminal.json',dict(complete=False,error=type(e).__name__,returncode=child.returncode));raise
if __name__=='__main__':main()
