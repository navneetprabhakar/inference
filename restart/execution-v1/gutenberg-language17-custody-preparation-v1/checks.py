"""Synthetic collision/role/family controls only. No retained-corpus pass."""
import copy,json
import overlap_core as c

def run():
 out=[]
 def yes(name,fn,fail=False):
  try:fn()
  except (ValueError,AssertionError,KeyError,IndexError):
   if not fail:raise
   out.append({'check':name,'PASS':True});return
  if fail:raise AssertionError('accepted:'+name)
  out.append({'check':name,'PASS':True})
 w=['word'+str(i) for i in range(120)];idx=c.Index([' '.join(w),'unrelated tiny specimen'])
 yes('NFKC_casefold_same_frozen_normalizer',lambda:None if c.normalized('Ａusten, ELIZABETH!')=='austen elizabeth' else (_ for _ in ()).throw(AssertionError()))
 yes('exact_and_full5gram_near',lambda:None if idx.compare(' '.join(w))[0]['normalized_exact'] and idx.compare(' '.join(w))[0]['fivegram_Jaccard_gte_0p8']['jaccard']==1 else (_ for _ in ()).throw(AssertionError()))
 yes('different_length_32_nonzero_candidate_offset',lambda:None if 0 in idx.containment(w[37:69]) else (_ for _ in ()).throw(AssertionError()))
 yes('whole_13word_containment_nonzero_offset',lambda:None if 0 in idx.containment(w[47:60]) else (_ for _ in ()).throw(AssertionError()))
 yes('short_whole_equality',lambda:None if 1 in idx.containment('unrelated tiny specimen'.split()) else (_ for _ in ()).throw(AssertionError()))
 yes('unrelated_refused',lambda:None if not idx.compare('xyznonsense repeated sample') else (_ for _ in ()).throw(AssertionError()))
 lines=['0\ta b c d e f g h i j k l'];ids=['protected:development:1'];units=[{'ordinal':0,'identity':ids[0],'role':'protected-never-added-to-training','normalized_text_sha256':c.sha(lines[0].split('\t')[1].encode())}]
 yes('disjoint_CPP_namespaces',lambda:None if c.reconcile_protections(lines,ids,units)[0][0]==1000000 and 1000000 not in range(1,5) else (_ for _ in ()).throw(AssertionError()))
 yes('missing_protected_unit_refused',lambda:c.reconcile_protections([],ids,units),True)
 v=copy.deepcopy(units);v[0]['identity']='other';yes('swapped_identity_refused',lambda:c.reconcile_protections(lines,ids,v),True)
 v=copy.deepcopy(units);v[0]['role']='train';yes('protected_role_loss_refused',lambda:c.reconcile_protections(lines,ids,v),True)
 # A raw-source/current-unit alias can never override an actual protected role.
 yes('protected_ancestor_collision_wins',lambda:None if c.disposition(True,True)=='PROTECTED_FAMILY_HOLD' else (_ for _ in ()).throw(AssertionError()))
 families={'candidateA':'work1','candidateB':'work1'};holds={families['candidateA']};yes('whole_family_propagation',lambda:None if [x for x,f in families.items() if f in holds]==['candidateA','candidateB'] else (_ for _ in ()).throw(AssertionError()))
 import tempfile,subprocess,pathlib
 with tempfile.TemporaryDirectory() as tmp:
  d=pathlib.Path(tmp);candidate=d/'candidate';protection=d/'protection';output=d/'output';text=' '.join(w[:32]);candidate.write_text(text+'\n');program=c.REPO/'restart/corpus-audit-v1/containment'
  protection.write_text('1\t'+text+'\n');subprocess.run([str(program),str(protection),str(candidate),str(output)],check=True,capture_output=True,timeout=5);assert not output.read_text()
  protection.write_text('1000000\t'+text+'\n');subprocess.run([str(program),str(protection),str(candidate),str(output)],check=True,capture_output=True,timeout=5);assert output.read_text().startswith('1\t1000000\t')
  yes('actual_CPP_sameID_self_skip_reproduced_and_disjointID_detected',lambda:None)
 import sources
 required={'adapter':'native_or_plain_UTF8_file','required_current_candidate_body_coverage':True};optional={**required,'required_current_candidate_body_coverage':False}
 yes('optional_raw_alias_cannot_discharge_required_candidate_coverage',lambda:None if sources.alias_signature(required,'samehash')!=sources.alias_signature(optional,'samehash') else (_ for _ in ()).throw(AssertionError()))
 return {'status':'PASS_SYNTHETIC_ONLY_NO_RETAINED_SCAN','count':len(out),'checks':out}
if __name__=='__main__':print(json.dumps(run(),indent=2))
