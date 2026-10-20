# Creator: Navneet Prabhakar
import json
import pytest
from slm.data import mixture, review
from slm.data.english_foundation_adapter import (
    build_mixture, build_curriculum, CurriculumBatches, FoundationMixtureBatches,
)
from slm.data.english_corpus import build_tokens
from slm.data.stream_hash import sha
from slm.common.tokenizer import train_core
from slm.common.training import Recipe
from slm.common.curriculum import CurriculumTrainer
from slm.common.config import Config, initialize
from test_english_corpus import record, text


def prepared(tmp_path):
    rows = [record(0, text('alpha')), record(1, text('beta'))]
    bpe = train_core([r['text'] for r in rows], 300)
    tok = tmp_path / 'tokenizer'; bpe.save(tok, {'scope': 'synthetic fixture'})
    path = tmp_path / 'tokens'
    result = build_tokens(rows, bpe, path, 'a'*64, sha(tok/'manifest.json'), 'b'*64, context=32)
    cs = [dict(id='general', path=path, dataset_hash=sha(path/'manifest.json'),
               weight=1, max_passes=2, max_positions=2*result['processed_positions'])]
    mix = tmp_path / 'mixture'
    built = build_mixture(cs, tok, mix, objective='foundation', budget=10000,
                          minimum=100, group_cap=10000, allowed_categories=('unreviewed',))
    return cs, tok, mix, built


def test_private_unreviewed_path_preserves_original_category_registry(tmp_path):
    original = set(review.CATEGORIES)
    cs, tok, path, built = prepared(tmp_path)
    with FoundationMixtureBatches(path, {'general': cs[0]['path']}, tok, built['dataset_hash']) as data:
        assert data.counts(len(data))[0] == built['planned_processed_positions']
        assert built['planned_processed_positions'] == 2*built['unique_prepared_processed_positions']
    assert review.CATEGORIES == mixture.CATEGORIES == original
    assert 'unreviewed' not in original
    with pytest.raises(ValueError, match='categories'):
        mixture.MixtureBatches(path, {'general': cs[0]['path']}, tok)


@pytest.mark.parametrize('objective,categories', [('sft', ('unreviewed',)), ('foundation', ('sfw',))])
def test_private_adapter_cannot_relax_conversation_category_scope(tmp_path, objective, categories):
    with pytest.raises(ValueError, match='scope'):
        build_mixture([], tmp_path, tmp_path/'out', objective=objective, allowed_categories=categories)
    assert not (tmp_path/'out').exists()


def test_adapter_bound_curriculum_actual_tiny_cpu_resume_and_tamper_refusal(tmp_path):
    cs, tok, mix, built = prepared(tmp_path)
    schedule = dict(lr=.001, warmup_tokens=0, cooldown_tokens=0,
                    final_lr_fraction=1, accumulation_steps=2)
    path = tmp_path/'curriculum'; bindings = dict(language=dict(path=mix, components={'general': cs[0]['path']}))
    result = build_curriculum([dict(id='language', path=mix, components=bindings['language']['components'],
                                   dataset_hash=built['dataset_hash'], schedule=schedule)],
                              tok, path, recipe=Recipe(accumulation_steps=2), family_processed_cap=10000)
    with CurriculumBatches(path, bindings, tok, result['dataset_hash']) as data:
        config = Config(vocab_size=data.vocab_size)
        trainer = CurriculumTrainer(config, initialize(config), data, 'torch', 'cpu')
        trainer.update(); trainer.save(tmp_path/'checkpoint')
        resumed = CurriculumTrainer.resume(tmp_path/'checkpoint', data, 'torch', 'cpu')
        assert resumed.cursor == trainer.cursor and resumed.tokens == trainer.tokens
        assert resumed.update() == trainer.update()
    manifest = json.loads((mix/'manifest.json').read_text())
    manifest['english_foundation_adapter_sha256'] = '0'*64
    (mix/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='adapter'):
        FoundationMixtureBatches(mix, bindings['language']['components'], tok)
