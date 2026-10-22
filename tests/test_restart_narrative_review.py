import copy
import pytest
from slm.restart.narrative_review import prepare,assess
from slm.restart.generation_metrics import DIMENSIONS,diagnostics


class Tokenizer:
    vocab_size=512
    def encode(self,text):return [10]
    def decode(self,tokens):return ' '.join('word'+str(t) for t in tokens)


@pytest.fixture
def fixture():
    tokenizer=Tokenizer()
    items=[{'id':f'final:{i:03d}','prefix':f'Premise {i}.','prefix_token_ids':[10],'generation_seed':42+i} for i in range(100)]
    tokens=list(range(20,100));text=tokenizer.decode(tokens)
    outputs=[dict(id=item['id'],generated_token_ids=tokens+[1],text=text,stop_reason='eos',ended_with_eos=True,
        decode_policy='temperature-.7-top-p-.9-PCG64',seed=item['generation_seed'],execution_failure=False,
        diagnostics=diagnostics(text,ended_with_eos=True)) for item in items]
    context=dict(identity='run',schedule_sha256='schedule',step=1000,targets=3000000,
                 checkpoint_sha256='a'*64,event='final_research_evaluation')
    bundle={'context':context,'outputs':outputs};packet=prepare(items,bundle,tokenizer)
    reviews=[{'review_id':item['review_id'],'evidence_sha256':item['evidence_sha256'],'reviewer':'assistant',
        'scores':dict.fromkeys(DIMENSIONS,2),'premise_contradiction':False,
        'rationales':dict.fromkeys(DIMENSIONS,'Synthetic test rating only; no real model quality claim.')} for item in packet['items']]
    return items,bundle,tokenizer,packet,reviews


def test_randomized_complete_bound_proxy_review(fixture):
    items,bundle,tokenizer,packet,reviews=fixture
    assert packet==prepare(items,bundle,tokenizer)
    assert [r['source_id'] for r in packet['items']]!=[i['id'] for i in items]
    assert set(r['source_id'] for r in packet['items'])==set(i['id'] for i in items)
    result=assess(*fixture)
    assert result['passed'] and result['acceptable']==100
    assert 'not independent human' in result['scope']


@pytest.mark.parametrize('failures,passed',[(20,True),(21,False)])
def test_eighty_complete_acceptable_reviews_required(fixture,failures,passed):
    for review in fixture[-1][:failures]:review['premise_contradiction']=True
    result=assess(*fixture)
    assert result['passed'] is passed and result['acceptable']==100-failures


@pytest.mark.parametrize('fault',['missing','duplicate','reordered','pin','rubric','boolean_score','rationale','reviewer','packet'])
def test_missing_or_altered_reviews_cannot_pass(fixture,fault):
    items,bundle,tokenizer,packet,reviews=fixture
    if fault=='missing':reviews.pop()
    if fault=='duplicate':reviews[1]=copy.deepcopy(reviews[0])
    if fault=='reordered':reviews.reverse()
    if fault=='pin':reviews[0]['evidence_sha256']='b'*64
    if fault=='rubric':reviews[0]['scores'].pop('grammar')
    if fault=='boolean_score':reviews[0]['scores']['grammar']=True
    if fault=='rationale':reviews[0]['rationales']['grammar']=' '
    if fault=='reviewer':reviews[0]['reviewer']='independent human'
    if fault=='packet':packet['items'][0]['continuation']='repaired'
    with pytest.raises(ValueError):assess(*fixture)


def test_output_changes_invalidate_prior_review(fixture):
    items,bundle,tokenizer,packet,reviews=fixture
    bundle['outputs'][0]['generated_token_ids'][0]=101
    with pytest.raises(ValueError):assess(*fixture)


def test_repetition_forces_coherence_failure_even_with_high_rubric(fixture):
    items,bundle,tokenizer,_,_=fixture
    for output in bundle['outputs'][:6]:
        tokens=[20,21,22,23]*20;output['generated_token_ids']=tokens+[1]
        output['text']=tokenizer.decode(tokens);output['diagnostics']=diagnostics(output['text'],ended_with_eos=True)
    packet=prepare(items,bundle,tokenizer)
    reviews=[{'review_id':r['review_id'],'evidence_sha256':r['evidence_sha256'],'reviewer':'assistant',
        'scores':dict.fromkeys(DIMENSIONS,2),'premise_contradiction':False,'rationales':dict.fromkeys(DIMENSIONS,'Synthetic fixture rating.')} for r in packet['items']]
    result=assess(items,bundle,tokenizer,packet,reviews)
    assert result['acceptable']==94 and result['fourgram_failures']==6 and not result['passed']
    failed=[r for r in result['items'] if r['grade']['diagnostics']['fourgram_failure']]
    assert all(r['grade']['scores']['local_coherence']==0 for r in failed)
