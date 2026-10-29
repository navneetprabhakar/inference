import ast,hashlib,json,re,collections
from pathlib import Path
P=Path('restart/coherence-g0-2026-10-29');O=Path('restart/coherence-g0-v3-2026-10-29/overlap')
def norm(s):return re.sub(r'\s+',' ',str(s).casefold()).strip()
def sha(s):return hashlib.sha256(s if isinstance(s,bytes) else s.encode()).hexdigest()
def h(s):return sha(norm(s))
def leaves(x):
 if isinstance(x,dict):return [z for v in x.values() for z in leaves(v)]
 if isinstance(x,list):return [z for v in x for z in leaves(v)]
 return [str(x)]
def msgs(r):
 if 'messages' in r:return r['messages']
 if isinstance(r.get('turns'),list):return [m for t in r['turns'] for m in [dict(role='user',content=t['user']),dict(role='assistant',content=t['reference'])]]
 return []
raw=(P/'final-custody/private/final.jsonl').read_bytes();F=[json.loads(s) for s in raw.splitlines()];H=json.loads((P/'final-custody/overlap-hashes.json').read_text());pool=json.loads((P/'final-custody/pools.json').read_text());meta=json.loads((P/'final-custody/metadata.json').read_text())
source=(P/'final-custody/private/author.py').read_text();tree=ast.parse(source)
data=None
for n in ast.walk(tree):
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DATA' for t in n.targets):data=ast.literal_eval(n.value)
assert isinstance(data,dict)
fields=[line.split('|') for lines in data.values() for line in lines];fh={h(v) for fs in fields for v in fs}
computed=[dict(id=r['id'],source_family=r['source_family'],scenario_cluster=r['scenario_cluster'],normalized_conversation_sha256=h('\n'.join(m['content'] for m in msgs(r))),normalized_user_sha256=[h(m['content']) for m in msgs(r) if m['role']=='user'],normalized_reference_sha256=[h(m['content']) for m in msgs(r) if m['role']=='assistant']) for r in F]
assert computed==H and sha(raw)==meta['payload_sha256'] and fh==set(pool['person_time_object_assignment_hashes'])
final_conv={r['normalized_conversation_sha256'] for r in H};fu={v for r in H for v in r['normalized_user_sha256']};fr={v for r in H for v in r['normalized_reference_sha256']}
final_users=[norm(m['content']) for r in F for m in msgs(r) if m['role']=='user'];final_text='\n'.join(norm(m['content']) for r in F for m in msgs(r));final_families=set(pool['source_family_namespace'])
def grams(s,n):
 ts=s.split();return {tuple(ts[i:i+n]) for i in range(len(ts)-n+1)}
fg={n:set().union(*(grams(s,n) for s in final_users)) for n in [8,12,20]}
paths=['training/private/candidates.json','benchmarks/development.json','benchmarks/grammar_contrasts.json','benchmarks/grounded_choices.json','benchmarks/native_continuations.json'];result={}
for path in paths:
 rows=json.loads((P/path).read_text());ms=[msgs(r) for r in rows];users=[norm(m['content']) for rr in ms for m in rr if m['role']=='user'];refs=[norm(m['content']) for rr in ms for m in rr if m['role']=='assistant'];convs={h('\n'.join(m['content'] for m in rr)) for rr in ms if rr}
 # For readiness, inspect actual rendered prefixes, all choices, passages and questions (also control prefixes), excluding token IDs and rubric.
 if not users:
  for r in rows:
   users.extend(norm(r[k]) for k in ['prefix','passage','question'] if isinstance(r.get(k),str))
   users.extend(norm(v) for k in ['options','suffixes'] for v in r.get(k,[]))
   refs.extend(norm(v) for k in ['options','suffixes'] for v in r.get(k,[]))
   users.extend(norm(v) for k,v in r.get('controls',{}).items() if k.endswith('prefix') and isinstance(v,str))
 values=[v for r in rows for k in ['slot_assignment','concrete_values'] if k in r for v in leaves(r[k])];value_hashes={h(v) for v in values}
 text='\n'.join(users+refs);fields_present={h(v) for fs in fields for v in fs if norm(v) and re.search(r'(?<!\w)'+re.escape(norm(v))+r'(?!\w)',text)}
 families={str(r[k]) for r in rows for k in ['source_family','scenario_family','domain','scenario_cluster'] if k in r}
 namespace_matches=final_families&families
 # All fields of a final source record must occur inside a SINGLE other conversation/item to qualify as a reproduced concrete scenario assignment.
 full_matches=0
 item_texts=[' '.join(norm(m['content']) for m in rr) if rr else ' '.join(norm(r[k]) for k in ['prefix','passage','question'] if isinstance(r.get(k),str)) for r,rr in zip(rows,ms)]
 for fs in fields:
  meaningful=[norm(v) for v in fs if len(norm(v).split())>=2]
  if meaningful and any(all(v in t for v in meaningful) for t in item_texts):full_matches+=1
 result[path]=dict(rows=len(rows),file_sha256=sha((P/path).read_bytes()),conversation_hash_matches=len(convs&final_conv) if convs else None,conversation_items_compared=sum(bool(rr) for rr in ms),exact_user_or_readiness_fragment_hash_matches=len({h(v) for v in users}&fu),exact_reference_hash_matches=len({h(v) for v in refs}&fr),source_namespace_matches=sorted(namespace_matches),declared_concrete_value_hash_matches=len(value_hashes&fh),declared_concrete_unique_values=len(value_hashes),final_pool_field_hashes_found_as_bounded_substrings=len(fields_present),complete_final_source_record_multitoken_field_sets_reproduced=full_matches,shared_user_word_ngram_counts={str(n):len(fg[n]&set().union(*(grams(s,n) for s in users))) for n in fg})
report=dict(status='EXACT_OVERLAP_CHECK_COMPLETE_LIMITED_CLEARANCE_ONLY_FINAL_UNSEALED',scope=paths,final_payload_sha256=sha(raw),final_public_hash_inventory_verified=True,final_pool_inventory_verified=True,normalization='Python str.casefold(); re.sub(r"\\s+", " ", s); strip(); UTF-8 encode; SHA-256. Whole conversation concatenates ordered user AND reference contents with newline before normalization, with no role markers. Per-user and reference hashes normalize each content independently. No Unicode NFC/NFKC or punctuation stripping.',pool_definition='517 hashes are unique pipe-delimited DATA source-record field strings, not structured joint person/time/object assignment tuples. Recomputed using AST literal evaluation only; author script never executed. Therefore a generic matching field is not proof of shared concrete event assignment.',final_counts=dict(records=len(F),scenario_clusters=len({r['scenario_cluster'] for r in F}),source_records=len(fields),unique_user_hashes=len(fu),unique_reference_hashes=len(fr),source_fields=len(fh)),comparisons=result,limitations=['Scope is old G0 training candidates, development and three readiness assets only. Additional/new training or broad corpora require a fresh check before admission.','No exact multi-turn duplicate and no reproduced complete multi-token source-field set establishes only bounded lexical disjointness, not semantic independence.','Shared abstract correction, grounding, instruction and interruption structures are intentional task structures. Exact 8/12/20-word overlaps quantify surface structural reuse, not leakage by themselves.','The public assignment inventory hashes individual fields, including generic relations/answers, and cannot alone prove concrete joint-assignment disjointness. Full source-field reproduction test is conservative and may miss paraphrased scenarios, changed entities, subsets, or split information.','Readiness has no whole conversation representation: conversation overlap is null (not applicable). Readiness reference hashes compare all option/suffix strings, not merely correct choices. Training declared assignments cover only the explicitly supplied slot_assignment metadata; other lexical values are covered by full rendered-text field search.','Independent semantic comparison of every source scenario across corpora is not performed. Namespace disjointness does not prove source-family semantic independence.','Final is 240 functional adaptations from 40 source scenarios; inference must account for cluster dependence.','Custody is procedural same-user access, not cryptographic isolation. Private source DATA and final payload were processed on CPU with no utterances or reference values emitted.'],sealed=False,eligible_for_G5=False,all_G0_gates_pass=False)
(O/'report.json').write_text(json.dumps(report,indent=2)+'\n')
lines=['# G0 v3 custody overlap audit','','Bounded exact-overlap and source-field checks completed. Final remains restricted, unsealed and ineligible for G5; this report is not full G0 admission.','','Algorithm: '+report['normalization'],'','Assignment inventory: '+report['pool_definition'],'','| Compared corpus | Rows | Whole conversations | Users/readiness fragments | Reference hashes | Concrete value hashes | Complete source field sets | Shared 8/12/20-word user ngrams |','|---|---:|---:|---:|---:|---:|---:|---|']
for p,r in result.items():lines.append('| '+p+' | '+' | '.join(str(r[k]) for k in ['rows','conversation_hash_matches','exact_user_or_readiness_fragment_hash_matches','exact_reference_hash_matches','declared_concrete_value_hash_matches','complete_final_source_record_multitoken_field_sets_reproduced'])+' | '+str(r['shared_user_word_ngram_counts'])+' |')
lines+=['','Limitations:']+['- '+s for s in report['limitations']]
(O/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(report,indent=2))
