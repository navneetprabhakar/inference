import json
from pathlib import Path
from dataclasses import replace
import pytest
from slm.restart.numerical_segments import run
from slm.restart.segments import segments,collate
ROOT=Path(__file__).resolve().parents[1]/'restart/execution-v1'
DOCS=json.loads((ROOT/'numerical-fixtures-v1/long-documents.json').read_text())


def test_all_six_actual_data_cases(tmp_path):
    result=run(DOCS,tmp_path)
    assert result['passed'] and len(result['cases'])==6 and result['neural_work_positions']==0
    expected={c['id'] for c in json.loads((ROOT/'numerical-suite-design-v1.json').read_text())['cases'] if c['group']=='segmentation'}
    assert set(result['cases'])==expected


@pytest.mark.parametrize('fault,case',[('shift','bos_target_shift'),('eos','single_document_eos'),('overlap','long_document_unique_targets'),('predecessor','one_predecessor_context'),('identity','family_split_identity_retained')])
def test_segment_mutations_are_detected(tmp_path,fault,case):
    def damaged(doc,content,context):
        parts=list(segments(doc,content,context))
        if doc=='fixture:1025':
            p=parts[1]
            if fault=='shift':p=replace(p,targets=(15,)+p.targets[1:])
            if fault=='eos':p=replace(p,targets=(1,)+p.targets[1:])
            if fault=='overlap':p=replace(p,first=p.first-1)
            if fault=='predecessor':p=replace(p,inputs=(15,)+p.inputs[1:])
            if fault=='identity':p=replace(p,document='other-family')
            parts[1]=p
        return parts
    result=run(DOCS,tmp_path,segmenter=damaged)
    assert not result['passed'] and not result['cases']['segmentation:'+case]['passed']


def test_padding_count_mutation_detected(tmp_path):
    def damaged(rows):
        x,y,m,spans=collate(rows);m[:]=1;return x,y,m,spans
    assert not run(DOCS,tmp_path,collator=damaged)['cases']['segmentation:padding_not_counted']['passed']
