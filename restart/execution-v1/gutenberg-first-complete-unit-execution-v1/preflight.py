"""Actual project runtime/import/artifact check before once-only source job."""
import argparse,json,sys,pathlib,subprocess,hashlib
import run
ap=argparse.ArgumentParser();ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);a=ap.parse_args();p=run.verify(a.code_pins_sha256,a.profile_sha256);rules,tokenizer=run.runtime(p)
raw=b'Heading\r\n\r\nThis is a complete synthetic English paragraph used only to check the installed language detector and tokenizer before source processing.\r\n';text=raw.decode('utf8');assert text.encode()==raw and '\r\n' in text
windows=list(rules.windows(text));assert len(windows)==2 and all(w['scored'] for w,t in windows);projected=[rules.projection(t) for w,t in windows];assert all('\n' not in t and '\r' not in t for t in projected)
ids=tokenizer.encode(text,add_special_tokens=False).ids;assert ids and all(0<=i<8182 for i in ids)
r=subprocess.run([str(run.FAST),'predict-prob',str(run.MODEL),'-','1'],input=('\n'.join(projected)+'\n').encode(),capture_output=True,timeout=5,check=True);lines=r.stdout.decode().splitlines();assert len(lines)==2
for line in lines:rules.prediction(line)
result={'status':'PASS_ACTUAL_PROJECT_RUNTIME_SYNTHETIC_ONLY','code_pins_sha256':a.code_pins_sha256,'profile_sha256':a.profile_sha256,'python':sys.version,'executable':sys.executable,'tokenizers_version':'0.22.2','frozen_M1_loaded_without_fit':True,'synthetic_UTF8_CRLF_roundtrip':True,'synthetic_scored_lines':2,'synthetic_native_predictions':lines,'tokenizer_ids_valid':True,'source_units_copied':0,'source_units_scored':0,'new_admitted_documents':0,'model_weights_initialized':0}
(run.HERE/'preflight-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
