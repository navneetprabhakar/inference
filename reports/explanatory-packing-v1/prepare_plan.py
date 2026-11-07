"""Metadata-only plan preparation after root review; does not execute packing."""
import hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parents[2];H=pathlib.Path(__file__).parent
PROSE=['feasibility-v1','extended-trial-v1','extended-trial-v2','extended-trial-v3','balanced-continuation-v1','base-foundation-100m']
SFT=['sft-readiness-v3','own-base-tool-candidates','own-base-tool-session-extension-v1','grounded-chat-candidates-v1','grounded-tool-candidates-v2','grounded-session-candidates-v2']
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 decision='reports/cosmopedia-candidates-v1/packing-decision.json';q=json.loads((R/decision).read_text());assert sha(R/decision)=='df898dc512aa6d12f616c7edaf129f4fa56dcfb3a299296796b5c415b020a723'
 names=set(q['pins'])|{decision,'reports/explanatory-packing-v1/build.py','reports/explanatory-packing-v1/prepare_plan.py','reports/explanatory-packing-v1/PROTOCOL.md','reports/explanatory-packing-v1/check_policy.py','reports/cosmopedia-candidates-v1/policy.json','reports/cosmopedia-intake-v1/plan.json','data/cosmopedia-intake-v1/receipt.json','tokenizer.py','stratified_language_validation.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe','data/narrative-candidates-v1/candidates.sqlite','data/narrative-candidates-v1/candidate-manifest.json','data/narrative-candidates-v1/candidate-verification.json','data/narrative-candidates-v1/public-custody-binding.json','reports/narrative-quality-v1/packing-decision.json'}
 names|={'data/cosmopedia-explanatory-candidates-v1/'+n for n in ('candidates.sqlite','receipt.json','candidate-verification-v2.json','custody.json')}
 sft=['data/'+n+'/candidates.sqlite' for n in SFT];names.update(sft)
 for n in PROSE:
  d=R/'data'/n;m=json.loads((d/'manifest.json').read_text());names.update(str(p.relative_to(R)) for p in [d/'manifest.json',d/'documents.jsonl']);names.update(str((d/(k+'.u16')).relative_to(R)) for k in m['shards'])
 missing=[n for n in sorted(names) if not(R/n).is_file()];assert not missing,('missing pinned input',missing)
 custody=json.loads((R/'data/cosmopedia-explanatory-candidates-v1/custody.json').read_text());assert custody['state']=='screened_not_admitted'
 p=dict(state='approved_for_cpu_packing_only',training_admitted=False,quality_decision=decision,historical_prose=PROSE,historical_sft_databases=sft,split_salt='forge-explanatory-language-split-v1',order_salt='forge-explanatory-pack-v1',pins={n:sha(R/n) for n in sorted(names)},limits=dict(seconds=1800,rss_bytes=3*1024**3,output_bytes=1024**3,free_disk_bytes=20*1024**3),scope='Full surviving pool once. Historical prepared prose supersets plus original/grounded SFT whole-history candidates and both narrative partitions. No private case access; root custody separately pinned.')
 with (H/'plan.json').open('x') as f:json.dump(p,f,indent=2);f.write('\n')
 print(sha(H/'plan.json'))
if __name__=='__main__':main()
