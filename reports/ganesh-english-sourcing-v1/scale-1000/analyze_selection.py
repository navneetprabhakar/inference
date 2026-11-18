"""Describe supervision units and late-context positions; never claims model memory accuracy."""
import argparse,collections,hashlib,importlib.util,json,pathlib,statistics
P=pathlib.Path(__file__).resolve().parent;ROOT=P.parents[2]
s=importlib.util.spec_from_file_location('v',P/'verify_selection.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
def summary(xs):return {'min':min(xs),'median':statistics.median(xs),'max':max(xs)} if xs else None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('selection');args=ap.parse_args();file=pathlib.Path(args.selection);rows=[json.loads(l) for l in file.read_text().splitlines()];tok=v.RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
 probes=[];targets=[];starts=collections.Counter();origins=collections.Counter();family_mass=collections.Counter();lengths=collections.Counter()
 for row in rows:
  ms=row['messages'];n=len(ms)//2;lengths[n]+=1
  if row.get('generation',{}).get('interface')=='codex exec':
   assert row['generation']['requested_model']=='gpt-6.1-terra';origin='Codex CLI gpt-6.1-terra'
  elif row.get('provenance')=='upstream_synthetic':origin='public-source synthetic (Smol-SmolTalk)'
  elif row.get('provenance')=='original_synthetic' and row.get('source')=='original Codex authoring':origin='earlier parent-authored synthetic'
  else:raise ValueError('Unclassified provenance: '+row['group'])
  origins[origin]+=1
  e=v.encode_conversation(tok,ms,policies=[{'permit_calls':False,'allowed_names':[]}]*n,context=2048);family_mass[row['family']]+=sum(e['mask'])
  for m in ms:
   if m['role']=='assistant':targets.append(v.norm(m['content']));starts[' '.join(v.norm(m['content']).split()[:2])]+=1
  if not row.get('memory_probe_credit'):continue
  q=row['recall_probe'];support=q['support_turn'];probe=q['probe_turn'];assert probe-support-1>=2
  users=[x for x in e['spans'] if x['kind']=='user_start'];ends=[x for x in e['spans'] if x['kind']=='assistant_end'];answers=[x for x in e['spans'] if x['kind']=='assistant_text']
  gapms=ms[2*support:2*(probe-1)]
  probes.append({'group':row['group'],'focus':q['focus'],'support_turn':support,'probe_turn':probe,'intervening_complete_pairs':probe-support-1,'probe_assistant_native_start':answers[probe-1]['start'],'gap_native_tokens_with_policy_framing':users[probe-1]['start']-ends[support-1]['end'],'gap_content_tokens_without_policy_frames':sum(len(tok.encode(m['content'])) for m in gapms),'evidence_kind':row.get('memory_evidence_kind','reviewed_focus_retrieval_or_constraint_application')})
 result={'payload_sha256':v.sha(file),'sessions':len(rows),'assistant_turns':len(targets),'unique_normalized_assistant_texts':len(set(targets)),'repeated_text_occurrences':len(targets)-len(set(targets)),'generation_provenance_sessions':dict(origins),'family_target_mass':dict(family_mass),'exchange_count_histogram':dict(sorted(lengths.items())),'common_two_word_reply_openings':starts.most_common(15),'credited_probes':len(probes),'intervening_pairs':summary([p['intervening_complete_pairs'] for p in probes]),'native_probe_start':summary([p['probe_assistant_native_start'] for p in probes]),'gap_content_tokens':summary([p['gap_content_tokens_without_policy_frames'] for p in probes]),'gap_native_tokens':summary([p['gap_native_tokens_with_policy_framing'] for p in probes]),'limitations':['Reviewed supervision, not measured model recall accuracy.','Native positions include repeated authoritative policy framing; content-only gaps reported separately.','No3K/4K coverage claim; native2048 bound.','Family labels are not proof of independent scenario mechanisms.','Synthetic majority and repeated advisory style limit breadth; no claim this corpus alone yields conversational competence.','No training/replay exposures occurred.']}
 (P/'supervision-analysis.json').write_text(json.dumps(result,indent=2)+'\n');(P/'credited-memory-probes.json').write_text(json.dumps({'payload_sha256':v.sha(file),'probes':probes},indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
