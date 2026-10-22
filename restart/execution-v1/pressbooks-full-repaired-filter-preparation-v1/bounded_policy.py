"""Frozen policies joined without source edits, inference or silent event truncation."""
import importlib.util,json,zlib,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
structural=load('frozen_structural_v3b',BASE/'pressbooks-structural-repair-preparation-v3b/policy.py')
component=load('frozen_component_v1',BASE/'pressbooks-component-detector-preparation-v1/component_core.py')
MAX_EVENTS=5000;MAX_JSON_BYTES=3000000

def evaluate(text,identity):
 s=structural.assess(text);c=component.detect_components(text,identity);v2=s['prior_v2'];v1=v2['prior_v1']
 groups=[v1['reasons'],v1['context_only_diagnostics'],v2['delta_representation_review_holds'],v2['delta_review_only_signals'],s['delta_representation_review_holds'],s['pending_dependency_queue'],c['flags']]
 events=sum(map(len,groups))
 if events>MAX_EVENTS:raise ValueError('combined_event_cap_no_truncation')
 mask=int(bool(groups[0]))|int(bool(groups[2]))*2|int(bool(groups[4]))*4
 queue=int(bool(groups[1] or groups[3] or groups[5]))|int(bool(groups[6]))*2
 result={'structural':s,'component_ancestry_review':c,'all_source_unchanged':True,'no_quality_or_admission_verdict':True,'source_JSON_SHA256_scope':'exact source physical JSONL line SHA including LF where present, verified by source-frame join; first samebody occurrence is receipt locator, alloccurrences retained separately'}
 raw=(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode()
 if len(raw)>MAX_JSON_BYTES:raise ValueError('lossless_joined_receipt_cap_no_truncation')
 packed=zlib.compress(raw,6)
 if len(packed)>MAX_JSON_BYTES:raise ValueError('compressed_receipt_cap')
 reasons={}
 for g in [groups[0],groups[2],groups[4]]:
  for f in g:reasons[f['reason']]=reasons.get(f['reason'],0)+1
 for g in [groups[1],groups[3],groups[5]]:
  for f in g:reasons['QUEUE:'+f['reason']]=reasons.get('QUEUE:'+f['reason'],0)+1
 for f in c['flags']:reasons['COMPONENT:'+f['kind']]=reasons.get('COMPONENT:'+f['kind'],0)+1
 return {'mask':mask,'queue_mask':queue,'events':events,'event_upper_bound':None,'JSON_bytes':len(raw),'JSON_SHA256':hashlib.sha256(raw).digest(),'zlib_bytes':packed,'zlib_SHA256':hashlib.sha256(packed).digest(),'codec':'zlib6-jsonUTF8-repaired-v1','reason_counts':reasons}
