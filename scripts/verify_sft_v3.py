"""Independent frozen data integrity, objective, coverage, and scoring checks."""
import collections,hashlib,json
import numpy as np
from tokenizers import Tokenizer
from sft_v3 import *
from evaluate_sft_v3 import evaluate_case,summarize
DATA=ROOT/'data/sft-v3';REPORT=ROOT/'reports/sft-v3'
def main():
 manifest=json.loads((DATA/'manifest.json').read_text());tok=Tokenizer.from_file(str(DATA/'tokenizer.json'));arrays=dict(np.load(DATA/'episodes.npz'));order=np.load(DATA/'order.npy');seen={};families={};records={};counts={};coverage={};gold=negative=0
 for path,receipt in zip([ROOT/'data/sft-v2/raw/smol-smoltalk.parquet',DATA/'raw/smol-smoltalk-1.parquet'],manifest['upstream_receipts']):
  assert path.stat().st_size==receipt['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==receipt['sha256']
 for name,digest in manifest['files'].items():assert hashlib.sha256((DATA/name).read_bytes()).hexdigest()==digest,name
 oldheldout=set();oldchat=set()
 for split in ['train','dev','test']:
  for line in (ROOT/f'data/sft-v2/{split}.jsonl').read_text().splitlines():
   r=json.loads(line)
   if split!='train':oldheldout.add(h(render(r['episode'])))
   if r['source']=='chat':oldchat.add(r['family'])
 losssets=dict(np.load(ROOT/'runs/evaluation-v1/loss_sets.npz'));protected={hashlib.sha256(np.asarray(row,np.int32).tobytes()).hexdigest() for key,a in losssets.items() if 'validation' in key or 'unseen' in key or 'untrained' in key for row in a}
 for split in ['train','dev','test']:
  rr=[json.loads(x) for x in (DATA/f'{split}.jsonl').read_text().splitlines()];records[split]=rr;counts[split]=dict(collections.Counter(r['kind'] for r in rr));slots=set();routes=set();errors=set();aliased=set();tool_names=set();counterfactuals=collections.defaultdict(list)
  for i,r in enumerate(rr):
   family=r['family'];assert family not in families or families[family]==split,(family,split);families[family]=split
   t,m,n=encode_record(tok,r);assert np.array_equal(t,arrays[split+'_ids'][i]);assert np.array_equal(m,arrays[split+'_mask'][i]);assert n==arrays[split+'_length'][i];assert m.sum()>0;assert t.min()>=0 and t.max()<16384
   if r['source']=='replay':
    assert split=='train' and r['objective']=='causal_lm' and n==513 and m.sum()==512
    assert hashlib.sha256(t.tobytes()).hexdigest() not in protected
    stream=np.memmap(r['provenance']['path'],dtype=np.uint16,mode='r');start=r['provenance']['block']*512;assert np.array_equal(t,np.asarray(stream[start:start+513],np.int32));key=hashlib.sha256(t.tobytes()).hexdigest()
   else:
    text=render(r['episode']);key=h(text);assert not m[n-1:].any();assert t[:n].tolist()==tok.encode(text).ids
    assert len(tok.encode(render(r['messages'],True)).ids)<=416
    if r['objective']=='final_assistant_only':
     prefix=len(tok.encode(render(r['episode'][:-1])).ids);assert not m[:prefix].any()
     assert tok.decode(t[1:][m.astype(bool)].tolist(),skip_special_tokens=False)==r['expected_answer']+EOS
    if split=='train':assert key not in oldheldout
    if split!='train' and r['source']=='chat':assert r['family'] not in oldchat
    if r['source']=='tool':
     assert 'tracking reference' not in text.casefold() and 'request reference' not in text.casefold()
     for j,c in enumerate(r.get('calls',[])):
      canonical=valid_call(r,c);tool_names.add(canonical['name'])
      if c['name'] in r['aliases']:aliased.add(canonical['name'])
      assert run_fixture(r,c,j)==r['results'][j]
      if canonical['name'] in ['calculate','convert']:assert execute(canonical)==r['results'][j]
     if r['kind']=='clarify':slots.add(r['missing_slot'])
     if r['kind']=='chain':routes.add(r['route'])
     if r['kind']=='error':errors.add(r['error_kind'])
     if r['kind']=='result':counterfactuals[family].append(r)
    if split!='train' and r['kind']!='chat':
     answers=iter([call_text(c) for c in r.get('calls',[])]+[r['expected_answer']]);result=evaluate_case(r,lambda messages:{'output':next(answers),'stop':'eos','repeated_4gram_fraction':0});assert result['success'],r['id'];gold+=1
     result=evaluate_case(r,lambda messages:{'output':'unrelated nonsense, zero city number?','stop':'eos','repeated_4gram_fraction':0});assert not result['success'],r['id'];negative+=1
   assert key not in seen or seen[key]==split,('cross split exact',r['id']);seen[key]=split
  pairs=sum(len(rs)==2 and rs[0]['provided_result']!=rs[1]['provided_result'] for rs in counterfactuals.values())
  assert slots==set(SLOT_ANSWERS),(split,slots);assert routes=={0,1,2,3};assert errors==set(ERROR_ANSWERS);assert tool_names==set(SCHEMAS)
  assert aliased==set(SCHEMAS),(split,aliased);assert pairs>0
  coverage[split]={'missing_slots':sorted(slots),'chain_routes':sorted(routes),'errors':sorted(errors),'tools':sorted(tool_names),'aliased_tools':sorted(aliased),'counterfactual_result_pairs':pairs}
 assert len(records['test'])==1000
 # Exact simulation of future 2M-slot budget, including partial updates/milestones.
 cursor=tokens=supervised=nonpad=0;exposures=[];source_real=collections.Counter();source_targets=collections.Counter();source_names={v:k for k,v in manifest['sources'].items()}
 for end in [1000000,2000000]:
  while tokens<end:
   count=min(8192,end-tokens);used=0
   while used<count:
    ix=order[cursor:cursor+2];assert len(ix)==2;width=int(max(arrays['train_length'][ix])-1);valid=min(width*2,count-used)
    for j,index in enumerate(ix):
     taken=min(width,max(0,valid-j*width));real=min(int(arrays['train_length'][index])-1,taken);targets=int(arrays['train_mask'][index,:taken].sum());source=source_names[int(arrays['train_source'][index])];source_real[source]+=real;source_targets[source]+=targets;nonpad+=real;supervised+=targets;exposures.append(int(index))
    cursor+=2;used+=valid
   tokens+=count
 result={'passed':True,'counts':counts,'coverage':coverage,'gold_scoring_cases':gold,'adversarial_negative_cases':negative,'cross_split_exact_overlap':0,'cross_split_family_overlap':0,'old_heldout_episodes_in_new_training':0,'replay_exact_protected_blocks':0,'fresh_chat_families_exclude_all_v2_chat':True,'objectives_and_masks_verified':True,'budget_simulation':{'processed_slots':tokens,'nonpadding_tokens':nonpad,'padding_fraction':1-nonpad/tokens,'supervised_tokens':supervised,'nonpadding_by_source':dict(source_real),'supervised_by_source':dict(source_targets),'real_token_mix':{s:n/nonpad for s,n in source_real.items()},'example_exposures':len(exposures),'unique_examples':len(set(exposures))},'training_started':False,'fresh_test_model_evaluations':0,'limitations':manifest['limitations']}
 (REPORT/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
