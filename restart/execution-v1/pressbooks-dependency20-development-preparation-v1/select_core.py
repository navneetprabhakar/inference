"""Development metadata qualification/priority only; never language or semantic inference."""
import hashlib,json,zlib
SEED='English-SLM-PB-dependency-salvage-development20-v1'
SETS={'A_MATH_ONLY':frozenset({'SOURCE_MATH_MARKUP_PRESERVED'}),'B_FIGURE_ONLY':frozenset({'FIGURE_REFERENCE_CONTEXT'})}
def decode(packed,packsha,rawsha,n):
 if len(packed)>3000000 or not 0<n<=3000000 or hashlib.sha256(packed).digest()!=packsha:raise ValueError('packed_receipt_binding')
 d=zlib.decompressobj();raw=d.decompress(packed,3000001)
 if not d.eof or d.unused_data or d.unconsumed_tail or len(raw)!=n or hashlib.sha256(raw).digest()!=rawsha:raise ValueError('lossless_receipt_binding')
 return json.loads(raw)
def stratum(row,receipt):
 if (row['language_pass'],row['explicit_known_hold'],row['generic_mask'],row['queue_mask'])!=(1,0,0,1):return None
 s=receipt['structural'];v2=s['prior_v2'];v1=v2['prior_v1'];c=receipt['component_ancestry_review']
 if c['flags'] or v1['reasons'] or v2['delta_representation_review_holds'] or s['delta_representation_review_holds']:return None
 reasons=frozenset(x['reason'] for g in [v1['context_only_diagnostics'],v2['delta_review_only_signals'],s['pending_dependency_queue']] for x in g)
 return next((k for k,v in SETS.items() if reasons==v),None)
def priority(k,h):
 if k not in SETS or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('identity')
 return hashlib.sha256((SEED+'\n'+k+'\n'+h).encode()).hexdigest()
def select(rows):
 groups={k:[] for k in SETS};seen=set()
 for r in rows:
  h=r['text_SHA256'];k=r['stratum']
  if h in seen:raise ValueError('duplicate_distinct_hash');
  seen.add(h);groups[k].append({**r,'priority_SHA256':priority(k,h)})
 if any(len(v)<10 for v in groups.values()):raise ValueError('insufficient_stratum_no_replacement')
 return [r for k in SETS for r in sorted(groups[k],key=lambda r:(r['priority_SHA256'],r['text_SHA256']))[:10]]
