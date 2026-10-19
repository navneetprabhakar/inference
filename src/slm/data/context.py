"""Derive immutable reference passages, never approve source answers or training."""
# Creator: Navneet Prabhakar
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.staging import canonical,metadata
from slm.data.tokenized import sha,stamp
from slm.data.quality_audit import PATTERNS

SOURCE='databricks/databricks-dolly-15k'
FUNCTION_WORDS=set('a an the is are was were in on at to of and or for from with by as that this it its has have not be been which'.split())
# Conservative scope exclusions, not classifiers or claims that the subjects
# themselves are inappropriate. Retain names/history unless a scoped term occurs.
SCOPE=re.compile(r'(?i)\b(?:symptoms?|diagnos\w*|medications?|prescri\w*|dosage|syndrome|disorder|disease|covid|cancer|suicide|porn\w*|sexual|sex|erotic\w*|retirement age|pension|investment advice|polling place)\b')
BOILERPLATE=re.compile(r'(?im)(?:\[citation needed\]|^\s*(?:vte|references|external links|see also)\s*$|<\/?[a-z][^>]{0,200}>)')


def checked_policy(policy):
    fields={'version','kind','status','source','parent_manifest_sha256','minimum_words','maximum_words',
            'minimum_latin_letter_fraction','minimum_function_word_types','maximum_url_occurrences','purpose','limitations'}
    if (set(policy)!=fields or type(policy['version']) is not int or policy['version']!=1
        or policy['kind']!='dolly-context-prose-candidate-v1' or policy['status']!='sample_only' or policy['source']!=SOURCE
        or not re.fullmatch('[a-f0-9]{64}',policy['parent_manifest_sha256'])
        or any(type(policy[k]) is not int or policy[k]<0 for k in ('minimum_words','maximum_words','minimum_function_word_types','maximum_url_occurrences'))
        or not 1<=policy['minimum_words']<=policy['maximum_words']<=10000
        or not 1<=policy['minimum_function_word_types']<=len(FUNCTION_WORDS)
        or type(policy['minimum_latin_letter_fraction']) not in (float,int)
        or not 0<policy['minimum_latin_letter_fraction']<=1):
        raise ValueError('Complete bounded context candidate policy required')


def derive(record,policy):
    """Exact context substring plus provenance; inherited split is a minimum."""
    if record['source']!=policy['source']:return None,'other_source'
    messages=record['messages']
    if len(messages)!=2 or [m['role'] for m in messages]!=['user','assistant']:return None,'unexpected_dialogue'
    prompt=messages[0]['content'];delimiter='\n\nContext:\n'
    if prompt.count(delimiter)!=1:return None,'missing_or_ambiguous_context'
    offset=prompt.index(delimiter)+len(delimiter);text=prompt[offset:]
    if not text or text!=text.strip() or unicodedata.normalize('NFC',text)!=text or '\ufffd' in text:return None,'noncanonical_context'
    if any(unicodedata.category(c)=='Cc' and c not in '\n\t' for c in text):return None,'controls'
    words=re.findall(r"[\w']+",text.casefold())
    if not policy['minimum_words']<=len(words)<=policy['maximum_words']:return None,'word_count'
    letters=[c for c in text if c.isalpha()]
    if not letters or sum('LATIN' in unicodedata.name(c,'') for c in letters)/len(letters)<policy['minimum_latin_letter_fraction']:return None,'script_proxy'
    if len(set(words)&FUNCTION_WORDS)<policy['minimum_function_word_types']:return None,'function_word_proxy'
    if SCOPE.search(text):return None,'scope_attention'
    if BOILERPLATE.search(text):return None,'boilerplate_attention'
    if any(pattern.search(text) for pattern in PATTERNS.values()) or '[EMAIL]' in text or '[PHONE]' in text:return None,'privacy_attention'
    if len(re.findall(r'https?://',text))>policy['maximum_url_occurrences']:return None,'url_attention'
    lines=[s.strip() for s in text.splitlines() if s.strip()]
    if len(lines)>5 and len(set(lines))<len(lines)*.8:return None,'repeated_lines'
    item=deepcopy(record);parent_hash=digest(record)
    item.update(example_id=record['example_id']+':context-prose-v1',messages=[dict(role='text',content=text)],
        task='prose',style='unlabeled',content_category='unreviewed',language='unknown',
        # An inherited held-out assignment is never weakened by re-grouping.
        official_split=record['split'],split=record['split'],lineage=[*record['lineage'],record['example_id']])
    item['validation_results']={'context_derivation':dict(version=1,method='exact-dolly-prompt-context-slice-v1',
        parent_example_id=record['example_id'],parent_record_sha256=parent_hash,parent_split=record['split'],
        parent_split_group=record['validation_results']['split_group'],prompt_character_start=offset,
        text_sha256=digest(text),policy_sha256=digest(policy)),
        'language_review':'required','privacy_review':'required','quality_review':'required','content_review':'required'}
    return item,None


def prepare(parent,policy_file,output):
    parent,policy_file,output=map(Path,(parent,policy_file,output))
    if output.exists():raise FileExistsError(output)
    verify(parent);policy=metadata(policy_file);checked_policy(policy)
    if sha(parent/'manifest.json')!=policy['parent_manifest_sha256']:raise ValueError('Candidate parent manifest differs')
    paths=[policy_file,*parent.iterdir(),Path(__file__)]
    before={p:stamp(p) for p in paths};seen=0;counts=Counter();splits=Counter();characters=Counter();fingerprints=[]
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.context-candidates-',dir=output.parent))
    try:
        with (temp/'candidates.jsonl').open('w') as out:
            for split in ('train','validation','test'):
                for shard in sorted(parent.glob(split+'-*.jsonl')):
                    for line in shard.open():
                        if len(line.encode())>1024*1024:raise ValueError('Context input row exceeds 1 MiB')
                        seen+=1
                        if seen>20000:raise ValueError('Context input exceeds 20000 rows')
                        record=json.loads(line)
                        if record['split']!=split:raise ValueError('Context input partition differs')
                        item,reason=derive(record,policy)
                        if reason:counts[reason]+=1;continue
                        out.write(canonical(item)+'\n');splits[split]+=1;characters[split]+=len(item['messages'][0]['content'])
                        fingerprints.append((item['example_id'],digest(item)))
        if not fingerprints:raise ValueError('No context candidates')
        if any(stamp(p)!=s for p,s in before.items()):raise ValueError('Context source or policy changed')
        result=dict(version=1,scope='sample_only',input_records=seen,candidate_records=len(fingerprints),splits=dict(splits),
            characters=dict(characters),exclusions=dict(counts),policy_sha256=digest(policy),
            parent_manifest_sha256=policy['parent_manifest_sha256'],candidate_identity_sha256=digest(fingerprints),
            candidates_sha256=sha(temp/'candidates.jsonl'),implementation_sha256=sha(__file__),
            answer_targets_retained=0,training_eligible=False,source_or_row_approvals=0)
        (temp/'policy.json').write_text(canonical(policy)+'\n');(temp/'report.json').write_text(canonical(result)+'\n')
        os.rename(temp,output);return result
    except BaseException:shutil.rmtree(temp,ignore_errors=True);raise
