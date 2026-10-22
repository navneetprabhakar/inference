"""Reproduce exact M0-train identity metadata preimage. No sourcebody/gold reads."""
from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent
def reproduce():
 spec=json.loads((HERE/'inventory-preimage-spec.json').read_text());source=Path(spec['source']['path']);raw=source.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=spec['source']['SHA256']:raise ValueError('source_metadata_changed')
 rows=[]
 for line in raw.decode('utf-8').splitlines():
  record=json.loads(line)
  if record['split']=='train':
   row=[record[k] for k in ['audit_id','family_id','original_text_sha256','normalized_sha256']]
   if any(type(v)is not str for v in row):raise ValueError('row_schema_str_only')
   rows.append(row)
 rows=sorted(rows,key=lambda row:str(row[0]))
 preimage=json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
 digest=hashlib.sha256(preimage).hexdigest()
 if len(rows)!=spec['expected_rows'] or digest!=spec['expected_SHA256']:raise ValueError('preimage_count_or_digest_mismatch')
 return {'status':'PASS_EXACT_METADATA_PREIMAGE_REPRODUCTION','rows':len(rows),'preimage_bytes':len(preimage),'SHA256':digest,'first_audit_id':rows[0][0],'last_audit_id':rows[-1][0],'source_metadata_SHA256':hashlib.sha256(raw).hexdigest(),'source_body_or_gold_bytes_read':0,'final_M2_or_probe_selection_created':False}
if __name__=='__main__':print(json.dumps(reproduce(),indent=2))
