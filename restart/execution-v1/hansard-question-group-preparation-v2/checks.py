import core,json
N=[]
def check(name,text,fn):
 parts=core.segment(text);assert ''.join(p['raw_text'] for p in parts)==text;assert sum(p['UTF8_end']-p['UTF8_start'] for p in parts)==len(text.encode());fn(parts);N.append(name)
def groups(p):return [x for x in p if x['kind']=='QUESTION_ANSWER_GROUP']
check('singleQA heading exactpartition',"Health: Services\n\nLord Ash: To ask Her Majesty's Government what happened.\n\nBaroness Birch: The service operated.\n",lambda p:len(groups(p))==1 or (_ for _ in ()).throw(AssertionError()))
text="Youth: Remand\n\nLord Beecham: To ask Her Majesty's Government how many.\n\nYouth: Remand\n\nLord Beecham: To ask Her Majesty's Government what proportion.\n\nLord Faulks: The proportion was27percent. Tables1–3 follow.\nLevels of Remand\n(Excel SpreadSheet,35KB)\n"
check('sharedtwoquestions ONEanswer no orphan and attachment retained',text,lambda p: (len(groups(p))==1 and groups(p)[0]['question_turns']==2 and groups(p)[0]['answer_turns']==1 and 'Excel' in groups(p)[0]['raw_text']) or (_ for _ in ()).throw(AssertionError()))
check('same-speaker Toask continuation stays withoneanswer',"Lord Ash: To ask the Chairman of Committees why.\n\tTo ask the Chairman of Committees when.\n\nLord Birch: Tomorrow.\n",lambda p:len(groups(p))==1 or (_ for _ in ()).throw(AssertionError()))
check('repeatedtopic AFTERanswer createsintactgroups',"Topic: One\n\nLord Ash: To ask why.\n\nLord Birch: Because it works.\n\nTopic: One\n\nLord Ash: To ask when.\n\nLord Birch: Tomorrow.\n",lambda p:len(groups(p))==2 or (_ for _ in ()).throw(AssertionError()))
check('questiononlyEOF held',"Lord Ash: To ask why.\n",lambda p:'QUESTION_WITHOUT_SUPPORTED_ANSWER' in groups(p)[0]['holds'] or (_ for _ in ()).throw(AssertionError()))
check('orphanreply+Unicode exact prefixkept',"Baroness Birch: Yes — déjà vu.\n\nHealth: Care\n\nLord Ash: To ask why.\n\nLord Birch: It helps.\n",lambda p:p[0]['kind']=='HELD_ORPHAN_PREFIX' or (_ for _ in ()).throw(AssertionError()))
check('reference-onlyrequiredcontext differs supplementalreference',"Lord Ash: To ask why.\n\nLord Birch: I refer the noble Lord to my earlier answer.\n",lambda p:'POSSIBLE_REFERENCE_ONLY_REQUIRED_CONTEXT_REVIEW' in groups(p)[0]['holds'] or (_ for _ in ()).throw(AssertionError()))
check('ambiguousheading ownership separateheldsidecar no arbitraryassign',"Lord Ash: To ask why.\n\nLord Birch: It helps.\n\nData unavailable\n\nLord Ash: To ask when.\n\nLord Birch: Tomorrow.\n",lambda p:any(x['kind']=='HELD_AMBIGUOUS_HEADING_OWNERSHIP' for x in p) or (_ for _ in ()).throw(AssertionError()))
check('no question entireorphan exactretention',"Unattributed fragment α\n",lambda p:p[0]['kind']=='HELD_ORPHAN_PREFIX' or (_ for _ in ()).throw(AssertionError()))
check('asked variant sourcegrammar',"Lord Ash asked Her Majesty's Government when.\n\nLord Birch: Tomorrow.\n",lambda p:len(groups(p))==1 or (_ for _ in ()).throw(AssertionError()))
check('ordinarytabletabs onlycontextflag notautomaticfail',"Lord Ash: To ask howmany.\n\nLord Birch: The rows are below.\nYear\tCount\n2020\t12\n",lambda p:not groups(p)[0]['holds'] or (_ for _ in ()).throw(AssertionError()))
check('unrecognizedspeakers notlaundered',"Alice: To ask why.\n\nBob: Because.\n",lambda p:not groups(p) or (_ for _ in ()).throw(AssertionError()))
check('empty attributedanswer is held',"Lord Ash: To ask why.\n\nLord Birch:\n",lambda p:'EMPTY_SUPPORTED_ANSWER_REVIEW' in groups(p)[0]['holds'] or (_ for _ in ()).throw(AssertionError()))
def require(ok):
 if not ok:raise AssertionError('boundary expectation')
qa="Lord Ash: To ask why.\n\nLord Birch: It helps.\n\n"
follow="Youth: Remand\n\nLord Beecham: To ask how many.\n\nYouth: Remand\n\nLord Beecham: To ask what proportion.\n\nLord Faulks: Tables1–3 Excel remain referenced.\n"
check('department after complete answer belongs exactsidecar not prioranswer',qa+'Ministry of Justice\n\n'+follow,lambda p:require(len(groups(p))==2 and len([x for x in p if x['kind']=='DEPARTMENT_CONTEXT_SIDECAR'])==1 and 'Ministry' not in groups(p)[0]['raw_text'] and groups(p)[1]['question_turns']==2 and groups(p)[1]['answer_turns']==1 and groups(p)[1]['department_context']['label']=='Ministry of Justice'))
check('initial department retained context then directquestion',"Home Office\n\n"+qa,lambda p:require(p[0]['kind']=='DEPARTMENT_CONTEXT_SIDECAR' and p[0]['following_group_parts']==[1]))
check('ordinary inline department mention not boundary',qa.replace('It helps.','The Ministry of Justice helps.')+follow,lambda p:require(not any(x['kind']=='DEPARTMENT_CONTEXT_SIDECAR' for x in p)))
check('unknown department not guessed',qa+'Department of Unobserved Matters\n\n'+follow,lambda p:require(not any(x['kind']=='DEPARTMENT_CONTEXT_SIDECAR' for x in p)))
check('unseparated known label not detached',qa+'Ministry of Justice\n'+follow,lambda p:require(not any(x['kind']=='DEPARTMENT_CONTEXT_SIDECAR' for x in p)))
check('known label quoted prose punctuation not detached',qa+'“Ministry of Justice”\n\n'+follow,lambda p:require(not any(x['kind']=='DEPARTMENT_CONTEXT_SIDECAR' for x in p)))
check('known label EOF retained no nextquestion corroboration',qa+'Ministry of Justice\n\n',lambda p:require(not any(x['kind']=='DEPARTMENT_CONTEXT_SIDECAR' for x in p)))
# Metadata-sized synthetic fixture preserves all40 unknown sidecars plus both-question answer.
fixture='Home Office\n\n'+qa+''.join(f'Unknown Topic {chr(65+i//26)}{chr(65+i%26)}\n\n'+qa for i in range(40))+follow
check('40sidecars metadata fixture fullUTF8inverse no sourceapplication',fixture,lambda p:require(sum(x['kind']=='HELD_AMBIGUOUS_HEADING_OWNERSHIP' for x in p)==40 and groups(p)[-1]['question_turns']==2))

def lifecycle_controls():
 import run,signal,tempfile,types,os,time,hashlib
 from pathlib import Path
 from unittest.mock import patch
 signal.setitimer(signal.ITIMER_REAL,0)
 def refuse(fn):
  try:fn()
  except Exception:return
  raise AssertionError('must refuse')
 for snap in ['', '123 1 2\n','123 1 -1\n','123 1 2\n123 1 2\n']:
  refuse(lambda:run.rss(snap,os.getpid(),None))
 N.append('productionRSS emptymissingnegativeandduplicate snapshots refuse')
 with tempfile.TemporaryDirectory() as z:
  root=Path(z);out=root/'out';out.mkdir();source=root/'synthetic.utf8';source.write_bytes(b"Topic: Care\n\nLord Ash: To ask why.\n\nLord Birch: It helps.\n")
  start=run.clk();args=types.SimpleNamespace(start=start,parent=os.getppid(),profile_sha256='p',code_pins_sha256='c');r={'source_id':1,'ordinal':1,'path':str(source),'SHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'bytes':source.stat().st_size,'stat':run.ident(source.stat()),'known_parent_hold':'SYNTHETIC'};profile={'output':str(out),'sources':[r]}
  (out/'result.json').write_bytes(b' '*run.SLOT);(out/'ownership.json').write_text(json.dumps({'supervisor_PID':os.getppid(),'worker_PID':os.getpid(),'start':start,'profile_SHA256':'p','codepins_SHA256':'c'}))
  with patch.object(run,'verify',lambda a:profile),patch.object(run,'ROOT',root):run.worker(args)
  signal.setitimer(signal.ITIMER_REAL,0);result=json.loads((out/'result.json').read_text());assert result['sources'][0]['candidate_groups']==1;part=json.loads((out/result['sources'][0]['file']).read_text());assert ''.join(p['raw_text'] for p in part['parts']).encode()==source.read_bytes()
  N.append('actualsyntheticworker fullsourceFDhashstat exactpartition and postflight')
  r['SHA256']='0'*64
  with patch.object(run,'verify',lambda a:profile),patch.object(run,'ROOT',root):refuse(lambda:run.worker(args))
  signal.setitimer(signal.ITIMER_REAL,0);N.append('actualsyntheticworker sourcehashmismatch refuses')
  before={f.name:f.read_bytes() for f in out.iterdir()}
  with patch.object(run,'verify',lambda a:profile),patch.object(run,'ROOT',root):refuse(lambda:run.supervise(args))
  assert before=={f.name:f.read_bytes() for f in out.iterdir()};N.append('existingoutput preflight refuses withoutsourceoutputmutation')
 refuse(lambda:core.segment('x'*(core.MAX_BYTES+1)));N.append('sourcebytecap refusal no hidden truncation')
 refuse(lambda:core.segment('Lord Ash: To ask why.\r\n'));N.append('unsupportedlinecontrol failclosed')
lifecycle_controls()
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':len(N),'names':N,'retained_source_applications':0},indent=2))
