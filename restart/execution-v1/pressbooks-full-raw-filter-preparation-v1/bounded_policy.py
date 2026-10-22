"""Resource-only wrapper; frozen generic policy decisions unchanged."""
import json,re,zlib,hashlib
import policy
MAX_EVENTS=5000
MAX_JSON_BYTES=2000000

def bounded_count(pattern,text,budget):
 count=0
 for _ in re.finditer(pattern,text):
  count+=1
  if count>budget:raise ValueError('potential_policy_event_cap_before_frozen_policy')
 return count

def evaluate(text):
 # Tight upper bounds on every finding call, without allocating its event dict.
 upper=2 # catalogue and explicit linked-source index each create at most one
 patterns=[r'\(\s*(?:and|or|,)\s*\)',r'(?is)\[latex\]\s*\[/latex\]|\\\[\s*\\\]',r'(?m)^For the (?:relation|function|equation|matrix|expression)\s*\n(?=[ⓐⓑⓒ]|[a-z][.)]\s)',r'(?i)estimated to be about[ \t]*\n[ \t]*(?=However\b|Therefore\b|Thus\b)',r'\band[.]',r'\b(?:Figure|Fig\.)\s*(?:\([^)\n]*\)|\d[\w.:-]*)?',r'\[/?latex\]|\\\(|\\\[',r'(?mi)^(?:glossary|references|works cited|image attributions|attributions|further reading|key terms|summary)\s*$']
 for pattern in patterns:
  upper+=bounded_count(pattern,text,MAX_EVENTS-upper)
  if upper>MAX_EVENTS:raise ValueError('potential_policy_event_cap_before_frozen_policy')
 for m in re.finditer(r'[^\n]+',text):
  s=m.group()
  if re.match(r'^\s*//',s) and re.search(r'\bclass\s+[A-Za-z_]\w*\s*\{',s) and re.search(r'\bstatic\s+(?:void|[A-Za-z_]\w*)\s+\w+\s*\(',s) and ';' in s:upper+=1
  if upper>MAX_EVENTS:raise ValueError('potential_policy_event_cap_before_frozen_policy')
 result=policy.filter_raw(text);events=len(result['reasons'])+len(result['context_only_diagnostics'])
 if events>upper or events>MAX_EVENTS:raise ValueError('event_upper_bound_implementation_mismatch')
 raw=(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode()
 if len(raw)>MAX_JSON_BYTES:raise ValueError('lossless_policy_receipt_cap_no_truncation')
 packed=zlib.compress(raw,6)
 if len(packed)>MAX_JSON_BYTES:raise ValueError('compressed_receipt_cap')
 mask=0
 for r in result['reasons']:mask|=1<<list(policy.RULES).index(r['reason'])
 return {'mask':mask,'event_upper_bound':upper,'events':events,'JSON_bytes':len(raw),'JSON_SHA256':hashlib.sha256(raw).digest(),'zlib_bytes':packed,'zlib_SHA256':hashlib.sha256(packed).digest(),'codec':'zlib6-jsonUTF8-v1','reason_counts':{k:sum(v['reason']==k for v in result['reasons']) for k in policy.RULES}}
