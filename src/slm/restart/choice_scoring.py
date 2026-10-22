"""Fixed-denominator evaluation of complete alternative log probabilities."""
import math


def score(items,outputs):
    """Each output supplies per-token log probabilities for every alternative.

    Required lengths include EOS; no length normalization, repairs, best-of or
    dropping failed items. Equal token lengths are a dataset admission condition.
    Missing/nonfinite/malformed outputs and exact ties count as failures.
    Duplicate/unknown IDs invalidate the evaluation rather than choosing a copy.
    """
    by_id={}
    for item in items:
        key=item['id'];lengths=item['continuation_token_lengths']
        if key in by_id or len(lengths)<2 or len(set(lengths))!=1 or any(type(n) is not int or n<1 for n in lengths):
            raise ValueError('Invalid fixed evaluation items')
        if type(item['correct_index']) is not int or not 0<=item['correct_index']<len(lengths):
            raise ValueError('Invalid answer key')
        by_id[key]=item
    if not by_id:raise ValueError('Empty evaluation')
    records={}
    for output in outputs:
        key=output['id']
        if key not in by_id or key in records:raise ValueError('Unknown or duplicate result ID')
        records[key]=output
    judged=[];groups={}
    for key,item in by_id.items():
        output=records.get(key);reason=None;scores=None;prediction=None
        if output is None:reason='missing_output'
        elif output.get('error'):reason='execution_error'
        else:
            values=output.get('token_log_probabilities')
            lengths=item['continuation_token_lengths']
            if (not isinstance(values,list) or len(values)!=len(lengths)
                or any(not isinstance(v,list) or len(v)!=n+1 for v,n in zip(values,lengths))):
                reason='incomplete_alternative_or_eos'
            elif any(type(x) not in (int,float) or not math.isfinite(x) or x>0 for v in values for x in v):
                reason='invalid_log_probability'
            else:
                try:scores=[math.fsum(v) for v in values]
                except OverflowError:reason='nonfinite_score'
                if scores is not None:
                    if not all(math.isfinite(x) for x in scores):reason='nonfinite_score'
                    elif scores.count(max(scores))!=1:reason='tie'
                    else:prediction=scores.index(max(scores))
        correct=prediction==item['correct_index'] if reason is None else False
        subtype=item['subtype'];group=groups.setdefault(subtype,{'correct':0,'total':0})
        group['total']+=1;group['correct']+=int(correct)
        judged.append({'id':key,'correct':correct,'prediction':prediction,'scores':scores,'failure':reason})
    correct=sum(x['correct'] for x in judged)
    return {'correct':correct,'total':len(items),'accuracy':correct/len(items),'by_subtype':groups,'items':judged,
            'scope':'Full-continuation plus EOS scores; statistical/capability gates applied separately.'}
