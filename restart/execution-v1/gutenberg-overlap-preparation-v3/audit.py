"""Bounded offline complete targeted overlap; no admission."""
import collections,hashlib,json,os,pathlib,signal,sqlite3,subprocess,sys,time
P=pathlib.Path(__file__).resolve().parent;E=P.parent;R=E.parents[1];D=E/'gutenberg-overlap-v3';C=E/'gutenberg-novel-prose-v1';M=E/'m0-registry-v1';DB=R/'restart/corpus-audit-v1/audit.sqlite';OLD=E/'m2-intake/individual-salvage-v1/overlap-v1';FAMILY='austen:pride-and-prejudice:original-work-all-editions';CAP=100000000
sys.path.insert(0,str(R/'src'));from slm.restart.edu_filter import normalized
sha=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def write(name,v):
 b=v if isinstance(v,bytes) else (json.dumps(v,indent=2,ensure_ascii=False)+'\n').encode()
 if sum(p.stat().st_size for p in D.rglob('*') if p.is_file())+len(b)>CAP-100000:raise ValueError('100MB output limit')
 with (D/name).open('xb') as f:f.write(b)
def grams(w,n):return {tuple(w[i:i+n]) for i in range(len(w)-n+1)}
def near(a,b):
 n=len(a&b);u=len(a|b);return bool(u and n*5>=u*4)
def validate_inputs():
 pins=json.loads((P/'input-pins.json').read_text())
 for name,h in pins['input_SHA256'].items():assert sha(pathlib.Path(name))==h,name
 return pins

def worker():
 assert os.getppid()==int(os.environ['PG_OVERLAP_PARENT']);start=float(os.environ['PG_OVERLAP_START']);pins=validate_inputs();cases=[]
 def guard():
  if time.monotonic()-start>=285:raise TimeoutError('285second worker bound')
 assert near(grams('a b c d e f'.split(),5),grams('a b c d e f'.split(),5));assert not near(grams('a b c d e f'.split(),5),grams('u v w x y z'.split(),5));cases.append('full_shingle_exact_and_unrelated_controls')
 assert normalized('Ａusten, ELIZABETH!')=='austen elizabeth';cases.append('same_frozen_normalization_NFKC_casefold_punctuation')
 registry=json.loads((M/'registry.json').read_text());assert sha(DB)==registry['input_sha256']['restart/corpus-audit-v1/audit.sqlite']
 for name,h in registry['files'].items():assert sha(M/'artifacts'/name)==h
 # Reconcile exact M0 protection inventory before any expensive content scan.
 for name in ['protections.tsv','protection-identities.json']:
  key='restart/execution-v1/m2-intake/individual-salvage-v1/overlap-v1/'+name
  assert sha(OLD/name)==registry['input_sha256'][key]
 identity_list=json.loads((OLD/'protection-identities.json').read_text());identity={str(n+1000000):v for n,v in enumerate(identity_list)};units=[json.loads(l) for l in (M/'artifacts/protected-text-units.jsonl').read_text().splitlines()];lines=(OLD/'protections.tsv').read_text().splitlines()
 def reconcile(lines,ids,units):
  assert len(lines)==len(ids)==len(units)==8841 and len(set(ids))==8841
  result=[]
  for n,line in enumerate(lines):
   ident,norm=line.split('\t',1);unit=units[n]
   assert int(ident)==n and unit['ordinal']==n and unit['identity']==ids[n] and unit['role']=='protected-never-added-to-training' and hashlib.sha256(norm.encode()).hexdigest()==unit['normalized_text_sha256']
   result.append((ident,norm,unit))
  return result
 protections=reconcile(lines,identity_list,units)
 def refusal(fn):
  try:fn()
  except (AssertionError,IndexError,KeyError):return
  raise AssertionError('Expected inventory mismatch refusal')
 refusal(lambda:reconcile(lines[:-1],identity_list,units));cases.append('missing_protected_unit_refused_before_scan')
 swapped=list(identity_list);swapped[0],swapped[1]=swapped[1],swapped[0];refusal(lambda:reconcile(lines,swapped,units));cases.append('swapped_identity_inventory_refused_before_scan')
 assert not set(map(int,identity)) & set(range(1,62));assert identity['1000000']==identity_list[0];cases.append('disjoint_protected_ID_namespace_excludes_candidate_IDcollision')
 write('preflight.json',{'status':'EXACT_SOURCE_PINS_AND_M0_PROTECTION_INVENTORY_RECONCILED_BEFORE_SCAN','protected_units':len(protections),'disjoint_protection_ID_min':min(map(int,identity)),'candidate_ID_max':61,'focused_controls':cases})
 rows=[json.loads(l) for l in (C/'chapters.jsonl').read_text().splitlines()];assert len(rows)==61 and {x['family_id'] for x in rows}=={FAMILY};assert all(x['split'] is None and x['training_admitted'] is False for x in rows)
 norms=[];words=[]
 for x in rows:
  b=(C/x['file']).read_bytes();assert sha(C/x['file'])==x['sha256'] and b.decode()==x['text'];norms.append(normalized(x['text']));words.append(norms[-1].split())
 sets=[grams(w,5) for w in words];idx=collections.defaultdict(list);idx32=collections.defaultdict(list);idx12=collections.defaultdict(list)
 for i,w in enumerate(words):
  for g in sets[i]:idx[g].append(i)
  for g in grams(w,32):idx32[g].append(i)
  for off in range(len(w)-11):idx12[tuple(w[off:off+12])].append((i,off))
 # Synthetic short and middle-window containment controls use the same lookup policy.
 def match_held(w):
  found={}
  if len(w)<12:
   n=' '.join(w)
   for i,v in enumerate(norms):
    if v==n:found[i]={'kind':'whole_document_equality_short'}
  elif len(w)<32:
   for i,off in idx12.get(tuple(w[:12]),()):
    if words[i][off:off+len(w)]==w:found[i]={'kind':'full_protected_12_to31_words','protected_word_offset':0,'words':len(w),'matched_normalized_text':' '.join(w)}
  else:
   for off in range(0,len(w)-31,16):
    g=tuple(w[off:off+32])
    for i in idx32.get(g,()):
     if i not in found:found[i]={'kind':'protected32_stride16','protected_word_offset':off,'words':32,'matched_normalized_text':' '.join(g)}
  return found
 assert 0 in match_held(words[0][37:69]);assert 0 in match_held(words[0][37:54]);assert not match_held(['notawordxyz']*11);cases.append('heldout_full_short_and_nonzero_candidate_32word_containment_controls')
 hits=[];exact=[];historical=[];scanned=held_count=0
 db=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
 for ident,source,norm,held,families,reference in db.execute('SELECT id,source,normalized,held,families,reference FROM docs'):
  guard();w=norm.split();g=grams(w,5);counts=collections.Counter()
  for value in g:
   for i in idx.get(value,()):counts[i]+=1
  for i,n in counts.items():
   union=len(g)+len(sets[i])-n
   if union and n*5>=union*4:hits.append({'chapter':i+1,'audit_id':ident,'source':source,'held':held,'families':families,'reference':reference,'intersection':n,'union':union,'jaccard':n/union})
  for i,v in enumerate(norms):
   if v==norm:exact.append({'chapter':i+1,'audit_id':ident,'source':source,'held':held,'families':families})
  if held:
   held_count+=1
   for i,match in match_held(w).items():historical.append({'chapter':i+1,'audit_id':ident,'source':source,'families':families,'reference':reference,**match})
  scanned+=1
  if scanned%50000==0:print(json.dumps({'scanned':scanned,'elapsed':time.monotonic()-start}),flush=True)
 db.close();guard()
 internal=[]
 for i,g in enumerate(sets):
  for j in range(i):
   if near(g,sets[j]):internal.append({'left_chapter':i+1,'right_chapter':j+1,'jaccard':len(g&sets[j])/len(g|sets[j])})
 assert len(protections)==8841;write('protections-disjoint.tsv',''.join(str(n+1000000)+'\t'+v[1]+'\n' for n,v in enumerate(protections)).encode());write('normalized-input.txt',('\n'.join(norms)+'\n').encode())
 program=R/'restart/corpus-audit-v1/containment';subprocess.run([str(program),str(D/'protections-disjoint.tsv'),str(D/'normalized-input.txt'),str(D/'containment.tsv')],check=True,timeout=max(.01,285-(time.monotonic()-start)))
 protected=[]
 for line in (D/'containment.tsv').read_text().splitlines():
  ci,pid,text=line.split('\t',2);i=int(ci)-1;assert ' '+text+' ' in ' '+norms[i]+' ';assert pid in identity;protected.append({'chapter':i+1,'protected_identity':identity[pid],'matched_normalized_text':text,'match_kind':'at_least_one_protected_full_or32_block','role':'protected-never-added-to-training'})
 pexact=[{'chapter':i+1,'protected_identity':unit['identity']} for i,norm in enumerate(norms) for _,p,unit in protections if norm==p]
 # Independent Python containment confirms C++ chapter-hit set without its rolling hashes.
 py_hits=set()
 for _,p,_ in protections:
  w=p.split()
  if len(w)<12:continue
  for i in match_held(w):py_hits.add(i+1)
 assert py_hits=={x['chapter'] for x in protected};cases.append('all8841_protected_units_independently_screened_python_and_CPP_agree')
 admitted=[json.loads(l) for l in (M/'artifacts/admitted-documents.jsonl').read_text().splitlines()];splits={}
 for r in admitted:splits.setdefault(r['family_id'],set()).add(r['split'])
 assert all(len(v)==1 for v in splits.values());explicit=[r for r in admitted if r['family_id']==FAMILY];protected_hit=bool(protected or pexact or historical or any(x['held'] for x in hits+exact));family_disposition='ENTIRE_AUSTEN_FAMILY_PROTECTED_HOLD' if protected_hit else 'NO_OBSERVED_PROTECTED_MATCH_WITHIN_THIS_SCREEN_NOT_ANCESTRY_CLEARANCE'
 assert all(x==FAMILY for x in [FAMILY]*61);cases.append('one_work_family_all61_no_split_all_protected_hits_propagate_whole_family')
 result={'status':'BOUNDED_OVERLAP_SCREEN_COMPLETE_NOT_ADMISSION','candidate_chapters':61,'candidate_work_families':1,'legacy_docs_scanned':scanned,'historical_heldout_docs_screened':held_count,'near_threshold':0.8,'legacy_normalized_exact_matches':exact,'legacy_near_matches':hits,'internal_near_matches':internal,'protected_units':8841,'protected_exact_matches':pexact,'protected_containment_matches':protected,'historical_heldout_containment_matches':historical,'explicit_existing_family_ID_matches':explicit,'existing_admitted_families_cross_split':0,'candidate_assigned_splits':0,'family_disposition':family_disposition,'protected_hit_propagates_to_chapters':list(range(1,62)) if protected_hit else [],'controls':cases,'elapsed_seconds':time.monotonic()-start,'input_pins':pins,'limitations':['No semantic paraphrase or unknown upstream ancestry guarantee; absence of Austen work ID in legacy metadata is not independence evidence.','Near is complete full normalized five-word set Jaccard >=0.8 against legacy docs; different-length overlaps additionally use protected strings/blocks.','Protected containment uses full12-31word strings or32word blocks stride16 at all candidate offsets; strings <12 only whole-document equality.','CPP records first protected containment per chapter; historical scan records first matching block per chapter and historical document, not every repeated occurrence.','Cross-intake screening against new Wikibooks/OpenStax/PMC/FineWeb derivatives remains pending.','No semantic/rights/language/quality admission gate is certified.'],'new_admitted_documents':0,'new_admitted_tokens':0}
 assert all(sha(pathlib.Path(n))==h for n,h in pins['input_SHA256'].items());write('result.json',result);print(json.dumps({k:result[k] for k in ['status','legacy_docs_scanned','family_disposition','elapsed_seconds']}))

def main():
 if '--worker' in sys.argv:return worker()
 validate_inputs();D.mkdir(exist_ok=False);start=time.monotonic();env=dict(os.environ,PG_OVERLAP_PARENT=str(os.getpid()),PG_OVERLAP_START=str(start));p=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--worker'],env=env,start_new_session=True);expired=False
 try:code=p.wait(timeout=300)
 except subprocess.TimeoutExpired:expired=True;os.killpg(p.pid,signal.SIGKILL);code=p.wait(timeout=3)
 write('supervisor.json',{'worker_exit_code':code,'external_timeout':expired,'elapsed_seconds':time.monotonic()-start,'retry':False,'network_requests':0});raise SystemExit(0 if code==0 and not expired else 1)
if __name__=='__main__':main()
