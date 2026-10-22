"""17frame/long-WB/identity controls; no retained body comparisons."""
from pathlib import Path
import sys,json,tempfile,copy,subprocess
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import audit,overlap_core as core,sources

def run():
 result=[]
 def yes(n,v):assert v,n;result.append({'name':n,'PASS':True})
 c=json.loads((HERE/'candidates.json').read_text());yes('exact_frozen17_frame_hash',audit.sha(HERE/'candidates.json')=='1cb1dcbac5e661e94cd93a946e8964789a7c2ae9067d1184d462d5d2646e028c' and len(c)==17 and sum(x['bytes'] for x in c)==528920 and sum(x['M1_content_tokens_already_computed'] for x in c)==173812)
 yes('all17_metadata_lead_slots_bound_to_candidate_order',len(audit.METADATA_LEADS)==17 and [r['ebook_ID'] for r in json.loads((HERE/'metadata-leads.json').read_text())['records']]==[r['ebook_ID'] for r in c])
 entries=json.loads((HERE/'body-sources.json').read_text());yes('current837_not_stale781',len(entries)==837)
 original=json.loads((audit.BASE/'wikibooks-three-renewed-custody-preparation-v1/body-sources.json').read_text());yes('exact_same_currentbodyframe',entries==original)
 yes('all29_currentPGbodypaths_present',all(any(e['path']==str((audit.ROOT/'gutenberg-post1900-first-complete-units-v1'/r['file']).resolve()) and e['required_current_candidate_body_coverage'] for e in entries) for r in json.loads((audit.ROOT/'gutenberg-post1900-first-complete-units-v1/documents.json').read_text())['documents']))
 with tempfile.TemporaryDirectory() as tmp:
  t=Path(tmp);d=t/'gutenberg-four-longWB-delta-preparation-v1';d.mkdir();norm=' '.join(['word']*200001);record={'source_ordinal':7,'source_outer_page_id':8,'source_outer_revision_id':9,'source_family':'family','normalized_SHA256':core.sha(norm.encode()),'normalized_words':200001};(d/'measurement.json').write_text(json.dumps({'records':[record]}));metadata={'source_ordinal':7,'page_id':8,'revision_id':9,'family':'family'}
  with patch.object(audit,'BASE',t):
   yes('measured_longWB_compared_not_skipped',audit.approved_large_WB(norm,metadata));yes('longWB_identity_swap_refused',not audit.approved_large_WB(norm,{**metadata,'revision_id':10}));yes('longWB_family_swap_refused',not audit.approved_large_WB(norm,{**metadata,'family':'other'}));yes('longWB_hash_change_refused',not audit.approved_large_WB(norm+' changed',metadata))
  # Production C++ ID17 must not be treated as outside old4 slots.
  text=' '.join('word'+str(i) for i in range(40));(t/'candidates').write_text('\n'.join(['unrelated'+str(i) for i in range(16)]+[text])+'\n');(t/'protected').write_text('1000000\t'+text+'\n')
  subprocess.run([str(core.REPO/'restart/corpus-audit-v1/containment'),str(t/'protected'),str(t/'candidates'),str(t/'matches')],check=True,capture_output=True,timeout=5)
  yes('actual_CPP_candidate17_disjointnamespace',any(l.startswith('17\t1000000\t') for l in (t/'matches').read_text().splitlines()))
 for name,snapshot in [('empty',''),('missing','1 0 2'),('duplicate','77 1 2\n77 1 3'),('malformed','77 1 x'),('negative','77 1 -1'),('zeroroot','77 1 0')]:
  try:audit.parse_RSS_snapshot(snapshot,77)
  except ValueError:yes('RSS_failclosed_'+name,True)
  else:raise AssertionError('RSSaccepted:'+name)
 yes('RSS_transitive_tree',audit.parse_RSS_snapshot('77 1 2\n78 77 3\n79 78 4',77)==9*1024)
 yes('samefamilyhold_propagates_across_new17',core.disposition(True,True)=='PROTECTED_FAMILY_HOLD')
 return {'status':'PASS_17FRAME_CAPACITY_LONGWB_REVISION_CONTROLS_NO_CORPUS_SCAN','checks':len(result),'cases':result}
if __name__=='__main__':print(json.dumps(run(),indent=2))
