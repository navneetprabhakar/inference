import json,hashlib,pathlib,datetime,collections
D=pathlib.Path(__file__).resolve().parent
R=D.parent
S=R/'pressbooks-byte-anthology-middle25-independent-review-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(n,x):(D/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert sha(S/'review.json')=='12718f0297d3fe6232258fa2ec2b71b578e5d2f08354f915834a32385ebb6e23'
assert sha(S/'coverage.json')=='02f17d8da2867cd7b99d04dc15ee6ce2cf80c1b1f64d84f72f0c1c2289efe269'
x=read(D/'per-unit-draft.json');local=read(D/'coverage.json');middle=read(S/'coverage.json')
union=[dict(v,reader='/root/supply_investigation') for v in local]
for c in middle['chunks']:
 assert c['read_status']=='FULL_VISIBLE_UNTRUNCATED_READ'
 union.append({'source_id':2,'ordinal':25434,'source_SHA256':middle['source_text_SHA256'],'chunk':c['chunk'],'byte_start':c['source_UTF8_byte_span'][0],'byte_end':c['source_UTF8_byte_span'][1],'SHA256':c['SHA256'],'characters':c['characters'],'visible_output_inspected_without_truncation':True,'reader':'/root/milestone_audit'})
checks=[]
for u in x['units']:
 b=pathlib.Path(u['source_text_path']).read_bytes();assert len(b)==u['text_UTF8_bytes'] and hashlib.sha256(b).hexdigest()==u['text_SHA256']
 cs=sorted([v for v in union if (v['source_id'],v['ordinal'])==(u['source_id'],u['ordinal'])],key=lambda v:v['byte_start'])
 pos=0
 for v in cs:
  assert v['byte_start']==pos and v['source_SHA256']==u['text_SHA256'] and v['visible_output_inspected_without_truncation']
  assert hashlib.sha256(b[v['byte_start']:v['byte_end']]).hexdigest()==v['SHA256']
  assert len(b[v['byte_start']:v['byte_end']].decode())==v['characters'];pos=v['byte_end']
 assert pos==len(b)
 u['whole_review_completed_by_team']=True;u['reviewers']=sorted({v['reader'] for v in cs});u['reviewed_byte_coverage']=pos
 checks.append({'source_id':u['source_id'],'ordinal':u['ordinal'],'bytes':pos,'chunks':len(cs),'contiguous_no_gap_no_overlap':True,'source_and_chunk_hashes_verified':True,'readers':u['reviewers']})
large=next(u for u in x['units'] if u['ordinal']==25434)
large['verdict']='HOLD'
large['assessment']='Complete supplied authored anthology unit reviewed by two readers: supplier investigator chunks1–30 and56–80; independent milestone reviewer chunks31–55. Iliad abridged selections/summary bridges and Odyssey BooksI–XXIV form intelligible continuous literary narrative, ending with reconciliation/covenant. Intentional abridgement, catalogue passages, archaic wording and historical fictional bias are not extraction-corruption grounds. Recurrent malformed repeated/dropped/spurious wording appears across both readers’ spans and needs exact upstream fidelity comparison; no correction or OCR-cause inference applied. Flattened Iliad note1–22 callouts lack recovered definitions anywhere in the full supplied text. HOLD current representation for these fidelity/dependency issues, not genre/length/age. Preserve Laura J.Getty introduction, Samuel Butler translation, Rhonda Kelley Iliad editing and its CC BY-SA4 notice separately from Odyssey Public Domain notice; metadata license does not clear every modern component/edition. Historical/mythic violence, slavery, misogyny and religion are source context, not instructional endorsement. Editorial historical claims unverified. Potential Butler/Homer overlap with Gutenberg requires later family custody; no novelty/admission claim.'
large['independent_middle_review']={'path':str(S/'review.json'),'SHA256':sha(S/'review.json'),'coverage_path':str(S/'coverage.json'),'coverage_SHA256':sha(S/'coverage.json'),'findings_count':len(read(S/'review.json')['representation_findings'])}
counts=collections.Counter(u['verdict'] for u in x['units'])
assert sum(c['bytes'] for c in checks)==958917 and len(union)==99 and len(x['units'])==10
save('team-coverage-union.json',{'status':'COMPLETE_EXACT_BYTE_COVERAGE_TEN_UNITS','units':checks,'chunks':sorted(union,key=lambda v:(v['source_id'],v['ordinal'],v['byte_start'])),'total_UTF8_bytes':958917,'local_reader_bytes':706773,'independent_reader_bytes':252144,'two_reader_largest_unit_bytes':803253,'not_a_single_reader_whole_claim_for_largest':True})
proof=R/'pressbooks-development30-capture-terminal-independent-verification-v1/verification.json'
assert sha(proof)=='5474c749f8ba4c938c3d7757c11db8962e59b88f4c6807a1e0f08cee9b773926'
x.update({'status':'COMPLETE_FINITE_TEN_UNIT_TEAM_WHOLE_REVIEW_NO_ADMISSION','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict_counts':dict(counts),'total_UTF8_bytes_reviewed':958917,'team_coverage_union_SHA256':sha(D/'team-coverage-union.json'),'capture_terminal_proof':{'path':str(proof),'SHA256':sha(proof)},'scope':'Ten fixed UTF8-byte-weighted development draws; not tokenweighted, not fresh acceptance, not sourcewide yield or factual/rights certification. Draw roles and canonical capture occurrence preserved; no corpus version chosen. No text edited, model fit, admission or live count mutation.','upstream_provenance':'Five of ten are OpenStax-derived according to captured metadata (66819,70188,63247,49834,26974); PressBooks delivery is not independent upstream diversity for these works.','practical_next_step':'Preserve four research-quality proxies with component/version/family/factual flags; source-backed math/figure/note/wording repair before reconsidering six held current representations. No inferred repairs or whole-source rejection.'})
save('review.json',x)
files=['assignment.json','chunks.py','chunk-plan.json','coverage.json','notes-progress.json','per-unit-draft.json','finalize.py','team-coverage-union.json','review.json']
save('manifest.json',{'status':'FROZEN_REVIEW_PACKET','files':{n:{'bytes':(D/n).stat().st_size,'SHA256':sha(D/n)} for n in files},'external_pins':{str(S/n):sha(S/n) for n in ['review.json','coverage.json','manifest.json']}})
print(json.dumps({'review_SHA256':sha(D/'review.json'),'manifest_SHA256':sha(D/'manifest.json'),'coverage_union_SHA256':sha(D/'team-coverage-union.json'),'verdicts':dict(counts),'units':len(checks),'bytes':958917,'chunks':len(union)}))
