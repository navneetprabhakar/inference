"""Deterministic raw-output diagnostics; no text repair or candidate selection."""
import re

DIMENSIONS=('grammar','topical_continuity','entity_reference','causal_temporal','local_coherence')

def diagnostics(text,*,ended_with_eos):
    if not isinstance(text,str) or type(ended_with_eos) is not bool:
        raise ValueError('Raw text and explicit EOS status required')
    words=text.split()
    normalized=re.findall(r"[\w]+(?:['’][\w]+)?",text.casefold())
    grams=[tuple(normalized[i:i+4]) for i in range(max(0,len(normalized)-3))]
    repeated=(len(grams)-len(set(grams)))/len(grams) if grams else 0.
    sentences=[' '.join(re.findall(r'\w+',s.casefold())) for s in re.split(r'[.!?]+',text)]
    sentences=[s for s in sentences if s]
    counts={s:sentences.count(s) for s in set(sentences)}
    triples=sorted(s for s,n in counts.items() if n>=3)
    return {'whitespace_words':len(words),'repeated_fourgram_fraction':repeated,
            'fourgram_failure':repeated>.20,'threefold_sentence_failure':bool(triples),
            'repeated_sentences':triples,'early_eos_failure':ended_with_eos and len(words)<40,
            'requested_length_ok':80<=len(words)<=120,
            'normalization':'Whitespace words for length; casefolded Unicode words for fourgrams; punctuation-delimited normalized sentences.'}


def grade(text,*,ended_with_eos,scores,premise_contradiction):
    if (set(scores)!=set(DIMENSIONS) or any(type(v) is not int or not 0<=v<=2 for v in scores.values())
            or type(premise_contradiction) is not bool):
        raise ValueError('Complete five-dimension rubric and explicit contradiction label required')
    d=diagnostics(text,ended_with_eos=ended_with_eos)
    acceptable=(sum(scores.values())>=8 and min(scores.values())>0 and not premise_contradiction
                and d['requested_length_ok'] and not d['fourgram_failure'] and not d['threefold_sentence_failure']
                and not d['early_eos_failure'])
    return {'acceptable':acceptable,'rubric_total':sum(scores.values()),'scores':scores,
            'premise_contradiction':premise_contradiction,'diagnostics':d}


def copy_match(generated_ids,reference_ids):
    if (not isinstance(generated_ids,list) or not isinstance(reference_ids,list)
            or len(reference_ids)!=64 or any(type(x) is not int or x<0 for x in generated_ids+reference_ids)):
        raise ValueError('Generated token IDs and exactly 64 reference token IDs required')
    matched=0
    for a,b in zip(generated_ids,reference_ids):
        if a!=b:break
        matched+=1
    return {'exact_next_64_copy':matched==64,'reference_prefix_match_tokens':matched,
            'generated_tokens':len(generated_ids),'scope':'Exact reference continuation only; not a global training-corpus longest-match search.'}


def copy_gate(training,heldout):
    if len(training)!=100 or len(heldout)!=100:
        raise ValueError('Copy gate requires 100 training and 100 heldout results')
    def count(records):
        if any(type(r.get('exact_next_64_copy')) is not bool for r in records):
            raise ValueError('Missing or failed copy evaluation is not a non-copy')
        return sum(r['exact_next_64_copy'] for r in records)
    train=count(training);held=count(heldout);difference=train-held
    return {'training_copies':train,'heldout_copies':held,'difference_percentage_points':difference,
            'final_gate_pass':train<=5 and difference<=5,
            'automatic_copy_stop':train>5 and difference>5}
