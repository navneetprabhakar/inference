"""Independent read-only verification of committed partial artifacts; no rerender."""
import hashlib,json,pathlib,time
BASE=pathlib.Path(__file__).resolve().parents[1];HERE=pathlib.Path(__file__).resolve().parent;PREP=BASE/'enwiki-two-source-wikitext-preparation-v1';OUT=BASE/'m2-intake/enwiki-two-source-literal-prose-development-v1';SOURCE=BASE/'m2-intake/enwiki-native-20row-capture-v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 start=time.monotonic();checks=[];pin=json.loads((PREP/'code-pins.json').read_text());package=json.loads((PREP/'literal-recipes.json').read_text());worker=json.loads((OUT/'result.json').read_text());supervisor=json.loads((OUT/'supervisor.json').read_text());terminal_before={n:sha((OUT/n).read_bytes()) for n in ['result.json','supervisor.json','worker.log']}
 assert worker['status']=='TERMINAL_PARTIAL_TWO_SOURCE_DEVELOPMENT_NO_RETRY' and supervisor['worker_exit_code']==1
 assert supervisor['result_sha256']==terminal_before['result.json']
 assert not (OUT/'manifest.json').exists()
 for name,digest in pin['sha256'].items():assert sha(pathlib.Path(name).read_bytes())==digest
 checks.append({'check':'ALL19_frozen_input_pins_still_exact_after_failed_final_recheck','PASS':True,'input_count':len(pin['sha256'])})
 assert (OUT/'all20-original-decisions.json').read_bytes()==(PREP/'all20-original-decisions.json').read_bytes()==(SOURCE/'all20-native-decisions.json').read_bytes()
 checks.append({'check':'all20original_decisions_byte_identical','PASS':True})
 assert (OUT/'frozen-literal-recipes.json').read_bytes()==(PREP/'literal-recipes.json').read_bytes()
 for r in package['recipes']:
  stem='row-'+str(r['index_row_ordinal']);preview=(OUT/(stem+'.development-preview.utf8')).read_bytes();ancestry=json.loads((OUT/(stem+'.ancestry.json')).read_text());native=pathlib.Path(r['source_text_path']).read_bytes();inverse=ancestry['inverse_operations'];parts=[];cursor=0
  assert len(inverse)==len(r['operations'])
  for inv,expected in zip(inverse,r['operations']):
   a=inv['output_start_byte'];b=inv['output_end_exclusive_byte'];original=bytes.fromhex(inv['original_hex']);replacement=bytes.fromhex(inv['replacement_hex'])
   assert inv['source_start_byte']==expected['start_byte'] and inv['source_end_exclusive_byte']==expected['end_exclusive_byte'] and inv['original_hex']==expected['original_hex'] and inv['replacement_hex']==expected['replacement_hex'] and inv['operation']==expected['operation']
   assert cursor<=a<=b<=len(preview) and preview[a:b]==replacement and native[expected['start_byte']:expected['end_exclusive_byte']]==original
   parts.extend([preview[cursor:a],original]);cursor=b
  parts.append(preview[cursor:]);restored=b''.join(parts)
  assert restored==native and sha(restored)==r['source_text_SHA256'] and sha(preview)==ancestry['preview_SHA256'] and len(preview)==r['derivative_content_bytes_arithmetic_only']
  omissions=json.loads((OUT/(stem+'.omissions-and-dependencies.json')).read_text())
  assert omissions['complete_native_units']==r['complete_native_units'] and omissions['native_reference_occurrences']==r['reference_occurrences'] and omissions['native_reference_definitions']==r['native_citation_definitions']
  assert omissions['omitted_exact_source_spans']==[o for o in r['operations'] if o['replacement_hex']=='']
  checks.append({'check':r['title']+'_independent_inverse_and_ALLauthorized_ops_nativeunit_reference_omission_sidecars_exact','PASS':True,'preview_SHA256':sha(preview),'source_SHA256':sha(native),'preview_bytes':len(preview),'literal_operations':len(inverse)})
 assert terminal_before=={n:sha((OUT/n).read_bytes()) for n in terminal_before}
 assert time.monotonic()-start<30
 report={'status':'PASS_COMMITTED_PARTIAL_ARTIFACTS_ONLY_ORIGINAL_JOB_REMAINS_FAILED','checks':checks,'original_terminal_hashes':terminal_before,'failure_diagnosis':'worker(a) reused local a for unit byte offsets; the final verify(a.code_pins_sha256,...) saw an integer. Both previews and inverse/omission sidecars had already committed. No final COMPLETE or artifact manifest exists.','no_retry_or_source_modification':True,'whole_preview_texts_read_after_verification':False,'new_admitted_documents':0,'new_admitted_tokens':0,'actual_input_bytes_maximum':5000000,'elapsed_seconds':time.monotonic()-start}
 (HERE/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
