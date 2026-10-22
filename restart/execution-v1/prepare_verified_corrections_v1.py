"""Apply three exact, primary-evidence-backed corrections; no corpus admission."""
import hashlib,json,pathlib
from slm.common.tokenizer import BPE
from slm.restart.edu_filter import normalized
O=pathlib.Path(__file__).resolve().parent;I=O/'m2-intake';D=I/'verified-corrections-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if D.exists():raise FileExistsError('Preserve immutable corrections')
 source=I/'individual-salvage-v2/candidates.jsonl';assert sha(source)=='16a67c7b9001fb97dae38f02b23c856b473888a59383bc2c1aacb66244f3ded0'
 items=[json.loads(l) for l in source.read_text().splitlines()];tok=BPE.load(O/'tokenizer-8192')
 fixes=[(35,'Auguste Renoir (1840-1917)','Auguste Renoir (1841–1919)',['https://www.nga.gov/artists/1823-auguste-renoir']),
 (36,'he was elected a U.S. senator from Ohio in 1880.','he was elected a U.S. senator from Indiana in 1881.',['https://www.senate.gov/states/IN/senators.htm','https://www.in.gov/idoa/statehouse/notable-hoosiers-in-sculpture/benjamin-harrison/']),
 (37,'more than fifty years before the English landed at Jamestown','forty-two years before the English landed at Jamestown',['https://www.nps.gov/jame/faqs.htm','https://www.floridamuseum.ufl.edu/histarch/research/st-augustine/menendez/'])]
 rows=[]
 for candidate,old,new,urls in fixes:
  x=items[candidate];assert x['text'].count(old)==1;text=x['text'].replace(old,new,1);assert text.replace(new,old,1)==x['text']
  rows.append({'source':'fineweb_edu','source_cohort':'individual-salvage-v2','source_id':x['source_id'],'row_index':x['row_index'],'url':x['url'],'parent_candidate':candidate,'parent_text':x['text'],'parent_text_sha256':x['text_sha256'],'parent_normalized_sha':x['normalized_sha'],'parent_original_sha':x['original_sha'],'text':text,'original_sha':x['original_sha'],'normalized_sha':hashlib.sha256(normalized(text).encode()).hexdigest(),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'tokens':len(tok._core.encode(text).ids),'edit_log':[{'operation':'exact_replace_once','before':old,'after':new,'evidence_urls':urls}],'training_admitted':False,'pending':['renewed near/protected/family/language checks','whole corrected-document factual disposition','captured-text and derivative rights clearance','split assignment/release verification'],'scope':'Verified local error correction only; remaining factual claims and rights are not cleared.'})
 D.mkdir()
 with (D/'candidates.jsonl').open('w') as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 receipt={'status':'CORRECTED_DERIVATIVES_NOT_ADMITTED','documents':len(rows),'parent_content_tokens':sum(items[x['parent_candidate']]['tokens'] for x in rows),'content_tokens':sum(x['tokens'] for x in rows),'source_candidates_sha256':sha(source),'candidates_sha256':sha(D/'candidates.jsonl'),'tokenizer_manifest_sha256':sha(O/'tokenizer-8192/manifest.json'),'new_admitted_documents':0,'new_admitted_tokens':0,'scope':'Three exact source-evidenced edits, no invented continuation or model rewriting; derivatives remain tied to parent family.'}
 (D/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
