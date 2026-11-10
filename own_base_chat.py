"""Strict own-model chat using the exact astra-dialogue-v1 SFT framing.

No model loading, host answer fallback, semantic repair or permission inference.
Only the injected model generates assistant text; the real offline broker owns
execution and observed results. This module does not replace the live preview.
"""
from copy import deepcopy
import json

from dialogue import CONTEXT, VERSION, assistant_prompt, parse_assistant
from tokenizer import EOT
from tools import FIELDS, OPERATIONS, UNITS, FixtureSession

REPLY_BUDGET=256


def policy_text(permit_calls=True, allowed_names=None):
    """Stable host policy for one current turn, shared with teacher serialization."""
    if type(permit_calls)!=bool:raise ValueError('permit_calls must be a boolean')
    if isinstance(allowed_names,str):raise ValueError('allowed_names must be a collection of names')
    names=frozenset(FIELDS if allowed_names is None else allowed_names)
    if not names<=FIELDS.keys():raise ValueError('unknown tool in host policy')
    effective=sorted(names) if permit_calls else []
    schemas={}
    if 'calculate' in effective:
        schemas['calculate']=dict(arguments=['op','a','b'],operations=sorted(OPERATIONS))
    if 'convert' in effective:
        schemas['convert']=dict(arguments=['value','from','to'],units=sorted(UNITS))
    policy=dict(permit_calls=permit_calls,allowed_tools=effective,calls_per_turn=2,calls_per_session=4,tools=schemas)
    return ('Host policy for the current user turn; prior tool records may reflect earlier permissions. '
            'Tools are offline calculator/conversion fixtures, not external services. '
            'Use actual observed tool records when answering. Return exactly one JSON object: '
            '{"text":"your answer"} or {"call":{"name":"tool name","arguments":{...}}}. '
            'End the frame with EOT. Current policy: '+json.dumps(policy,sort_keys=True,separators=(',',':')))


def stable_tool_record(record):
    """Keep the complete observed record except volatile audit timestamp."""
    if type(record)!=dict:raise ValueError('tool record must be a dictionary')
    if not isinstance(record.get('call_id'),str) or not record['call_id']:
        raise ValueError('tool record lacks host call ID')
    if type(record.get('ok'))!=bool:
        raise ValueError('tool record lacks a boolean outcome')
    if record['ok']:
        if 'data' not in record or 'error' in record:raise ValueError('successful tool record requires only data')
    elif 'error' not in record or 'data' in record:raise ValueError('failed tool record requires only error')
    projected={key:deepcopy(value) for key,value in record.items() if key!='timestamp'}
    json.dumps(projected,ensure_ascii=False,allow_nan=False).encode('utf-8')
    return projected


class Chat:
    def __init__(self,model,tok,guard,*,generate=None,allowed_tools=('calculate','convert'),
                 reply_budget=REPLY_BUDGET,context=CONTEXT,repetition_penalty=1.):
        if not callable(getattr(guard,'check',None)):raise ValueError('a runtime guard is required')
        if type(reply_budget)!=int or reply_budget!=REPLY_BUDGET:
            raise ValueError('own-base chat reserves exactly256 reply tokens')
        if type(context)!=int or context!=CONTEXT:
            raise ValueError('own-base chat uses the complete1024-token context')
        if generate is None and model is None:raise ValueError('actual model required without explicit test callback')
        if generate is not None and not callable(generate):raise ValueError('generate callback must be callable')
        from repetition_decode import validate_penalty
        self.repetition_penalty=validate_penalty(repetition_penalty)
        self.model,self.tok,self.guard=model,tok,guard
        self.generate=generate
        self.reply_budget,self.context=reply_budget,context
        self.session=FixtureSession(allowed=frozenset(allowed_tools))
        self.history=[]
        self.turn_records=[]
        self.current_policy=None
        self.closed_reason=None

    def prompt_history(self):
        if self.current_policy is None:raise ValueError('no current turn policy')
        return [dict(role='system',text=self.current_policy)]+deepcopy(self.history)

    def _generate(self,prefix):
        if self.generate is not None:return self.generate(prefix,self.reply_budget)
        from repetition_decode import greedy
        return greedy(self.model,prefix,self.reply_budget,self.guard,repetition_penalty=self.repetition_penalty)

    def turn(self,user,permit_calls=True,allowed_names=None,fixture_for=None,fixture=None):
        start=len(self.session.trace)
        result=dict(answer=None,frames=[],trace=[],failure=None,failure_kind=None,frame_records=[],
                    selected_path='gpt2/'+VERSION,frame_origins=[])
        if self.closed_reason is not None:
            result['failure']='chat closed after prior failure: '+self.closed_reason
            result['failure_kind']='closed_session'
            self.turn_records.append(dict(user=user,result=deepcopy(result)))
            return result
        try:
            if not isinstance(user,str) or not user.strip():raise ValueError('nonempty user text required')
            user.encode('utf-8')
            if isinstance(allowed_names,str):raise ValueError('allowed_names must be a collection of names')
            scope=self.session.allowed if allowed_names is None else frozenset(allowed_names)
            # Pure policy validation occurs before resetting the broker turn.
            self.current_policy=policy_text(permit_calls,scope & self.session.allowed)
            self.session.start_turn(permit_calls=permit_calls,allowed_names=scope,
                                    fixture_for=fixture_for,fixture=fixture)
            self.history.append(dict(role='user',text=user))
            while True:
                self.guard.check()
                prefix=assistant_prompt(self.tok,self.prompt_history(),reply_budget=self.reply_budget,context=self.context)
                suffix=list(self._generate(prefix))
                frame=dict(generated_ids=suffix,context_tokens=len(prefix),
                           stop='eot' if suffix and suffix[-1]==EOT else 'reply cap')
                result['frame_records'].append(frame)
                if len(suffix)>self.reply_budget:raise ValueError('reply exceeds256-token budget')
                if any(type(token)!=int or not 0<=token<=EOT for token in suffix):
                    raise ValueError('invalid generated token ID')
                raw=self.tok.decode(suffix)
                frame['raw']=raw
                result['frames'].append(raw)
                result['frame_origins'].append('gpt2/'+VERSION)
                payload=parse_assistant(self.tok,suffix)
                frame['parsed']=deepcopy(payload)
                if 'text' in payload:
                    self.history.append(dict(role='assistant',text=payload['text']))
                    result['answer']=payload['text']
                    break
                # Quotas/permissions/schema/adapter errors remain the broker's
                # decision. A returned denial is observed data, not host prose.
                self.guard.check()
                observed=self.session.propose(json.dumps(payload['call'],ensure_ascii=False,allow_nan=False),
                                               assistant_call_boundary=True)
                authoritative=self.session.trace
                decisions=self.session.decisions
                if (not authoritative or observed!=authoritative[-1] or not decisions
                        or observed.get('call_id')!=decisions[-1]['call_id']):
                    raise ValueError('returned tool record differs from authoritative host binding')
                frame['tool_record']=deepcopy(observed)
                frame['broker_decision']=deepcopy(decisions[-1])
                candidate=self.history+[dict(role='assistant',call=deepcopy(payload['call']),call_id=observed['call_id']),
                                        dict(role='tool',record=stable_tool_record(observed))]
                # Validate proposal/result linkage and preserve the observed
                # records even if the next full reply cannot fit the context.
                self.history=candidate
                assistant_prompt(self.tok,self.prompt_history(),reply_budget=self.reply_budget,context=self.context)
        except (ValueError,TypeError) as error:
            result['failure']=str(error) or type(error).__name__
            result['failure_kind']='protocol'
            self.closed_reason=result['failure']
            result['answer']=None
        except Exception as error:
            # Guard stops, decoder/OOM errors and resource failures must remain
            # visible to the controller. Preserve real effects in finally and
            # close this uncertain session instead of fabricating an answer.
            result['failure']=str(error) or type(error).__name__
            result['failure_kind']='infrastructure'
            self.closed_reason=result['failure']
            result['answer']=None
            raise
        finally:
            result['trace']=self.session.trace[start:]
            self.turn_records.append(dict(user=user,policy=self.current_policy,result=deepcopy(result)))
        return result
