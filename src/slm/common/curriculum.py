"""Stage-aware FP32 trainer with global AdamW state and explicit LR clocks."""
from pathlib import Path
from slm.common.training import Trainer
from slm.data.curriculum import CurriculumBatches
from slm.data.tokenized import sha


def validate_progress(batches,recipe,step,cursor,tokens,supervised):
    if not isinstance(batches,CurriculumBatches) or recipe!=batches.base_recipe:
        raise ValueError('Curriculum and pinned base recipe required')
    if any(type(v) is not int or v<0 for v in (step,cursor,tokens,supervised)):
        raise ValueError('Invalid curriculum training counters')
    progress=batches.progress(cursor)
    if progress['global_updates']!=step or batches.counts(cursor)!=(tokens,supervised):
        raise ValueError('Inconsistent curriculum counters')
    return progress


class CurriculumTrainer(Trainer):
    SUPPORTS_CURRICULUM = True
    CHECKPOINT_SCHEDULE = 'curriculum-stage-warmup-stable-linear-cooldown-v1'
    def __init__(self,config,weights,batches,backend='torch',device='cpu',recipe=None,tokenizer_hash=None):
        if not isinstance(batches,CurriculumBatches):raise ValueError('Verified curriculum batches required')
        recipe=batches.base_recipe if recipe is None else recipe
        if recipe!=batches.base_recipe:raise ValueError('Recipe differs from pinned curriculum')
        super().__init__(config,weights,batches,backend,device,recipe,tokenizer_hash or batches.tokenizer_hash)

    def _update_context(self):
        recipe,end,_,_=self.batches.context(self.cursor)
        return recipe,end

    def _update_rate(self,recipe,end,tokens):
        return self.batches.rate(self.cursor,end)

    def _update_result(self,result,start_cursor):
        _,_,i,_=self.batches.context(start_cursor)
        row=self.batches.progress(result['cursor'])['stages'][i]
        return {**result,'stage':row['id'],'stage_cursor':row['cursor'],'stage_updates':row['updates'],
            'stage_processed_positions':row['processed_positions'],'stage_supervised_positions':row['supervised_positions'],
            'stage_completed':row['status']=='complete'}

    def _validate_progress(self):
        validate_progress(self.batches,self.recipe,self.step,self.cursor,self.tokens,self.supervised_tokens)

    def _checkpoint_extra(self):
        return {'version':3,'curriculum':self.batches.progress(self.cursor),
            'curriculum_trainer_sha256':sha(Path(__file__)),
            'schedule':'curriculum-stage-warmup-stable-linear-cooldown-v1',
            'accumulation':{'policy':'stage-specific-consume-tail-no-cross-stage-v1','pending_microbatches':0}}

    @staticmethod
    def _validate_state(state,batches,recipe):
        if state['version']!=3:raise ValueError('Curriculum requires version-3 training state')
        if (state.get('accumulation')!={'policy':'stage-specific-consume-tail-no-cross-stage-v1','pending_microbatches':0}
            or type(state['accumulation'].get('pending_microbatches')) is not int):
            raise ValueError('Unsupported curriculum accumulation policy')
        expected=validate_progress(batches,recipe,state['step'],state['cursor'],state['tokens'],state['supervised_tokens'])
        # Canonical JSON distinguishes booleans from integers as well as exact field sets.
        from slm.data.schema import digest
        if digest(state.get('curriculum'))!=digest(expected):raise ValueError('Curriculum progress receipt differs')

    @classmethod
    def resume(cls,path,batches,backend='torch',device='cpu',tokenizer_hash=None):
        return super().resume(path,batches,backend,device,tokenizer_hash or batches.tokenizer_hash)
