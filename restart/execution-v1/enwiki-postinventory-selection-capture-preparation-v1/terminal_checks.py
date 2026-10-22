"""Full terminal gate probes using only injected synthetic metadata/stat objects."""
import copy,json,tempfile,hashlib
from pathlib import Path
import terminal_guard as g
N=0
def ok(v):
 global N;assert v;N+=1
def no(fn):
 global N
 try:fn()
 except (ValueError,KeyError):N+=1;return
 raise AssertionError('expected refusal')
frame={'path':'/fixture/frame.sqlite','stat':[1,2,1024,4,5],'SHA256':'a'*64};header={'path':'/fixture/original-header.xml','stat':[1,3,128,4,5],'SHA256':'b'*64};codec={'path':'/fixture/codec.json','stat':[1,4,256,4,5],'SHA256':'c'*64};groups={'path':'/fixture/group-receipts.jsonl','stat':[1,5,512,4,5],'SHA256':'d'*64};index={'path':'/index','stat':[1,6,1024,4,5],'SHA256':'e'*64};prefix={'path':'/prefix','bytes':17988844772,'stat':[1,7,17988844772,4,5],'SHA256':'f'*64}
b={'status':g.STATUS,'producer_reaped':True,'verifier_reaped':True,'producer_exit_code':0,'verifier_exit_code':0,'frame':frame,'header':header,'codec':codec,'group_receipts':groups,'index':index,'prefix':prefix}
for k in ['producer_profile','producer_result','producer_supervisor','producer_ownership','verifier_result','verifier_supervisor','verifier_ownership','producer_terminal_binding']:b[k]={'id':k,'SHA256':g.PROF if k=='producer_profile' else '0'*64}
meta={
 'producer_profile':{'index':index,'source':prefix,'selection':{'compressed_prefix_end_exclusive':17988779480}},
 'producer_result':{'status':'COMPLETE_RETAINED_PREFIX_FRAGMENT_FRAME_NO_ADMISSION','profile_SHA256':g.PROF,'codepins_SHA256':g.PINS,'whole_publisher_archive_verified':False,'counts':{'pages':15840694,'groups':158433,'revision_occurrences':15840694,'ns0_nonredirect':12000000}},
 'producer_supervisor':{'status':'COMPLETE_RETAINED_PREFIX_FRAGMENT_NO_ADMISSION','worker_exit_code':0,'result_SHA256':'0'*64},
 'producer_ownership':{'worker_PID':123,'supervisor_PID':124,'profile_SHA256':g.PROF,'codepins_SHA256':g.PINS},
 'verifier_result':{'status':'COMPLETE_INDEPENDENT_STORED_FRAGMENT_METADATA_VERIFICATION_NO_ADMISSION','publisher_whole_archive_verified':False,'producer_binding_SHA256':'0'*64,'pages':15840694,'groups':158433,'revisions':{'observed':15840694,'expected':15840694},'ns0_nonredirect_pending_only':12000000,'output_hashes':{'frame.sqlite':'a'*64,'original-header.xml':'b'*64,'codec.json':'c'*64,'group-receipts.jsonl':'d'*64}},
 'verifier_supervisor':{'status':'COMPLETE_STORED_METADATA_VERIFICATION','worker_exit_code':0,'result_SHA256':'0'*64},
 'verifier_ownership':{'worker_PID':125,'supervisor_PID':126,'profile_SHA256':g.VPROF,'codepins_SHA256':g.VPINS},
 'producer_terminal_binding':{'status':'PARENT_REVIEWED_COMPLETE_TERMINAL_METADATA_BINDING','producer_reaped':True,'producer_exec_exit_code':0,'producer_owned_PIDs_absent':True,'files':{n:x for n,x in [('frame.sqlite',frame),('original-header.xml',header),('codec.json',codec),('group-receipts.jsonl',groups)]}}}
stat={x['path']:x['stat'] for x in [frame,header,codec,groups,index,prefix]};load=lambda e:meta[e['id']]
ctx=g.validate(b,load,lambda p:stat[p],lambda pid:True);ok(ctx['status']=='VERIFIED_TERMINAL_CONTEXT_NO_SOURCE_BODY_OPENED');ok(ctx['whole_publisher_archive_verified'] is False)
for field,value in [('status','UNBOUND'),('producer_reaped',False),('verifier_reaped',False),('producer_exit_code',1),('verifier_exit_code',1)]:
 bad=copy.deepcopy(b);bad[field]=value;no(lambda:g.validate(bad,load,lambda p:stat[p],lambda pid:True))
no(lambda:g.validate(b,load,lambda p:stat[p],lambda pid:pid!=123))
for key,field,value in [('producer_result','status','PARTIAL'),('producer_result','whole_publisher_archive_verified',True),('verifier_result','status','PARTIAL'),('verifier_result','pages',15840693),('verifier_result','producer_binding_SHA256','9'*64),('producer_ownership','codepins_SHA256','9'*64),('verifier_ownership','profile_SHA256','9'*64)]:
 original=meta[key][field];meta[key][field]=value;no(lambda:g.validate(b,load,lambda p:stat[p],lambda pid:True));meta[key][field]=original
no(lambda:g.validate(b,load,lambda p:[0]*5,lambda pid:True))
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp).resolve()/'metadata.json';raw=b'{"fixture":"metadata only"}\n';p.write_bytes(raw);e={'path':str(p),'SHA256':hashlib.sha256(raw).hexdigest()};ok(g.load_metadata(e)=={'fixture':'metadata only'});e['SHA256']='0'*64;no(lambda:g.load_metadata(e))
print(json.dumps({'status':'PASS_SYNTHETIC_TERMINAL_GATES_ONLY','controls':N,'real_producer_metadata_SQL_or_native_reads':0}))
