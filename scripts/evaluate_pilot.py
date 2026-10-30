"""Local generation and broader loss diagnostics; frozen prompts, no tuning."""
import hashlib,json,math,sqlite3,time,sys
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
import mlx.core as mx
import mlx.nn as nn
from tokenizers import Tokenizer
from benchmark_mlx import Model
from prepare_pilot import normalized,digest
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/pilot-v1';OUT=ROOT/'runs/evaluation-v1';REPORT=ROOT/'reports/evaluation-v1'
PROMPTS=[
 ('story','Once upon a time, a little girl found a lost puppy. She decided to'),
 ('causal_story','Tom put an ice cube in a bowl and left it in the sun. After an hour,'),
 ('explanation','Plants need sunlight because'),
 ('adult_prose','When planning a project, it is important to identify the main risks. For example,'),
 ('conversation','User: Hi, how are you?\nAssistant:'),
 ('instruction','User: Give me three tips for staying organized at work.\nAssistant:'),
 ('grounded','Context: Maya lives in Pune and works as a teacher.\nQuestion: Where does Maya live?\nAnswer:'),
 ('arithmetic','Question: What is 7 plus 5?\nAnswer:'),
 ('clarification','User: What is the weather like?\nAssistant:'),
 ('tool','Available tool: get_weather(city: string). Return only JSON with name and arguments.\nUser: What is the weather in Bengaluru?\nAssistant:'),
 ('tool_example','User: Weather in Mumbai?\nAssistant: {"name":"get_weather","arguments":{"city":"Mumbai"}}\nUser: Weather in Pune?\nAssistant:'),
 ('tool_result','User: What is 7 plus 5?\nTool result: {"result":12}\nAssistant:')]
def save(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
def checkpoint(phase):
 r=ROOT/'runs/local-campaign-v1'/phase
 return r/json.loads((r/'latest.json').read_text())['directory']/'model.safetensors'
def load(kind):
 mx.random.seed(43);m=Model(768,12,16384)
 if kind!='random':m.load_weights(str(checkpoint('benchmark' if kind=='5m' else 'pilot')))
 m.set_dtype(mx.bfloat16);mx.eval(m.parameters());return m

def build_sets(tok):
 rng=np.random.default_rng(20261030);sets={};provenance={}
 for source in ['fineweb','tinystories']:
  arr=np.memmap(DATA/f'{source}-validation.bin',dtype=np.uint16,mode='r')
  # Skip the beginning consulted repeatedly during training; select disjoint blocks.
  indices=rng.choice(np.arange(32,(len(arr)-1)//512),128,replace=False)
  sets[source+'_validation']=np.stack([np.asarray(arr[i*512:i*512+513],dtype=np.int32) for i in indices]);provenance[source+'_validation']={'blocks':indices.tolist(),'prior_monitor_prefix_excluded':True}
 c=sqlite3.connect(f'file:{DATA / "documents.sqlite"}?mode=ro',uri=True)
 seen=set();rows=json.loads((ROOT.parent/'inference-archive-20261029/restart/mac15m-feasibility-v1/upstream/data/TinyStories_all_data/data02.json').read_text())
 candidates={ 'tinystories_unseen_shard':[(r['story'],None) for r in rows] }
 wiki=ROOT.parent/'inference-archive-20261029/restart/execution-v1/m2-intake/raw/79ee06627f4ba2fec056fcd23c077a29238bbcbacc3187e8d1a0b47e663e9c7a.parquet'
 table=pq.read_table(wiki,columns=['text']);candidates['wikipedia_untrained_source']=[(x,None) for x in table['text'].to_pylist()]
 for name,records in candidates.items():
  selected=[];hashes=[]
  for i in rng.permutation(len(records)):
   text,_=records[i];h=digest(normalized(text))
   if h in seen or c.execute('SELECT 1 FROM docs WHERE hash=?',(h,)).fetchone():continue
   ids=tok.encode(text).ids
   if len(ids)<513:continue
   selected.append(ids[:513]);hashes.append(h);seen.add(h)
   if len(selected)==128:break
  assert len(selected)==128
  sets[name]=np.asarray(selected,dtype=np.int32);provenance[name]={'normalized_document_sha256':hashes,'screen':'Excluded exact matches against entire pilot document index, including unused rows. Near-duplicate/cross-source passage overlap not excluded.'}
 # Match actual exposed training blocks, reconstructed from saved sampler cursor.
 phase=ROOT/'runs/local-campaign-v1/pilot';state=json.loads((phase/json.loads((phase/'latest.json').read_text())['directory']/'state.json').read_text())
 for source in ['fineweb','tinystories']:
  arr=np.memmap(DATA/f'{source}-train.bin',dtype=np.uint16,mode='r');salt=0 if source=='fineweb' else 100000
  order=np.random.default_rng(43+salt).permutation((len(arr)-1)//512);assert state['corpus']['epochs'][source]==0
  sampled=rng.choice(order[:state['corpus']['cursors'][source]],128,replace=False)
  sets[source+'_exposed_train']=np.stack([np.asarray(arr[i*512:i*512+513],dtype=np.int32) for i in sampled]);provenance[source+'_exposed_train']={'blocks':sampled.tolist(),'training_diagnostic_not_heldout':True}
 c.close();np.savez(OUT/'loss_sets.npz',**sets);save(REPORT/'evaluation-set.json',{'seed':20261030,'provenance':provenance,'tokens_per_set':65536,'method':'128 blocks, each 512 scored next-token targets, context at most 512. Entire document prefix for new-source sets. Not a public benchmark.'});return sets

def score(m,arr):
 values=[]
 for i in range(0,len(arr),4):
  t=mx.array(arr[i:i+4]);v=nn.losses.cross_entropy(m(t[:,:-1]).astype(mx.float32),t[:,1:],reduction='none').mean(axis=1);mx.eval(v);values.extend(v.tolist())
 avg=float(np.mean(values));return {'nll_nats_per_token':avg,'perplexity':math.exp(avg),'block_mean_standard_error':float(np.std(values,ddof=1)/math.sqrt(len(values))),'blocks':len(values),'tokens':len(values)*512}

def generate(m,tok,prompt,mode,seed,max_tokens=96):
 mx.random.seed(seed);ids=tok.encode(prompt).ids;output=[];eos=tok.token_to_id('<|endoftext|>');start=time.monotonic();stop='length'
 for _ in range(max_tokens):
  logits=m(mx.array([ids[-512:]]))[0,-1].astype(mx.float32)
  if mode=='greedy':next_id=int(mx.argmax(logits))
  else:
   kth=mx.sort(logits)[-40];logits=mx.where(logits>=kth,logits/0.8,-float('inf'));next_id=int(mx.random.categorical(logits))
  if next_id==eos:stop='eos';break
  output.append(next_id);ids.append(next_id)
 text=tok.decode(output,skip_special_tokens=False);grams=[tuple(output[i:i+4]) for i in range(max(0,len(output)-3))]
 return {'output':text,'generated_tokens':len(output),'stop':stop,'seconds':time.monotonic()-start,'repeated_4gram_fraction':1-len(set(grams))/len(grams) if grams else 0.}
def main():
 OUT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
 tok=Tokenizer.from_file(str(DATA/'tokenizer.json'));save(REPORT/'prompts.json',PROMPTS);sets=build_sets(tok)
 results={'checkpoints':{},'scores':{},'limitations':['5M checkpoint is a separate seed/run, not a longitudinal checkpoint of the pilot.','Loss sets are modest diagnostics, not independent capability benchmarks.','Chat/tool prompts are zero-shot diagnostics of a base model with no SFT.','No cloud or paid API calls.']}
 for kind in ['random','5m','100m']:
  m=load(kind);results['scores'][kind]={}
  if kind!='random':results['checkpoints'][kind]={'path':str(checkpoint('benchmark' if kind=='5m' else 'pilot')),'sha256':hashlib.sha256(checkpoint('benchmark' if kind=='5m' else 'pilot').read_bytes()).hexdigest()}
  for name,arr in sets.items():
   result=score(m,arr);results['scores'][kind][name]=result;print(kind,name,json.dumps(result),flush=True);save(REPORT/'loss-results.json',results)
  if kind=='100m':
   samples=[]
   for number,(category,prompt) in enumerate(PROMPTS):
    for mode in ['greedy','sampled']:
     sample={'category':category,'prompt':prompt,'decoding':mode,'seed':100+number,**generate(m,tok,prompt,mode,100+number)};samples.append(sample);save(REPORT/'generations.json',samples);print('GEN',json.dumps(sample),flush=True)
  del m;mx.clear_cache()
if __name__=='__main__':main()
