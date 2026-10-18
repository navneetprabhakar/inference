"""Byte-level BPE candidates with disjoint structural/content ID namespaces."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from importlib.metadata import version
from tokenizers import Tokenizer, models, pre_tokenizers, decoders, trainers
from slm.data.review import training_examples
from slm.data.schema import digest
from slm.common.config import Config

STRUCTURAL = {name:i for i,name in enumerate((
    'bos','eos','pad','message_end','system','user','assistant','tool',
    'tool_call_start','tool_call_end'))}
OFFSET = len(STRUCTURAL)
ROLES = {'system','user','assistant','tool'}
PRETOKENIZER = {'type':'ByteLevel','add_prefix_space':False,'trim_offsets':True,'use_regex':True}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def train_core(texts, vocab_size, min_frequency=2):
    """Low-level builder; callers own corpus eligibility. No structural tokens added."""
    if type(vocab_size) is not int or vocab_size < OFFSET+256 or type(min_frequency) is not int or min_frequency<1:
        raise ValueError('Vocabulary must cover all bytes plus structural IDs; positive frequency required')
    core=Tokenizer(models.BPE())
    core.pre_tokenizer=pre_tokenizers.ByteLevel(add_prefix_space=False,use_regex=True)
    core.decoder=decoders.ByteLevel()
    core.train_from_iterator(texts,trainers.BpeTrainer(vocab_size=vocab_size-OFFSET,
        min_frequency=min_frequency,initial_alphabet=sorted(pre_tokenizers.ByteLevel.alphabet()),show_progress=False))
    return BPE(core)


class BPE:
    def __init__(self,core):
        raw=json.loads(core.to_str());model=raw['model']
        if (raw['added_tokens'] or raw['normalizer'] is not None or raw['post_processor'] is not None
            or raw['truncation'] is not None or raw['padding'] is not None
            or raw['pre_tokenizer']!=PRETOKENIZER or raw['decoder']['type']!='ByteLevel'
            or model['type']!='BPE' or model['dropout'] is not None or model['unk_token'] is not None
            or model['continuing_subword_prefix'] is not None or model['end_of_word_suffix'] is not None
            or model['fuse_unk'] or model['byte_fallback'] or model['ignore_merges']):
            raise ValueError('Unsupported tokenizer conventions')
        vocab=core.get_vocab()
        if (set(vocab.values())!=set(range(len(vocab)))
            or not set(pre_tokenizers.ByteLevel.alphabet())<=set(vocab)):
            raise ValueError('Complete contiguous byte vocabulary required')
        # Clone to prevent callers from mutating a validated tokenizer after construction.
        self._core=Tokenizer.from_str(core.to_str())
        self.vocab_size=len(vocab)+OFFSET

    def encode(self,text):
        if not isinstance(text,str):raise ValueError('Text must be a string')
        text.encode('utf-8')  # reject unpaired surrogates rather than silently replacing them
        return [i+OFFSET for i in self._core.encode(text,add_special_tokens=False).ids]

    def decode(self,ids):
        ids=list(ids)
        if any(type(i) is not int or not OFFSET<=i<self.vocab_size for i in ids):
            raise ValueError('Content decoding refuses structural or out-of-range IDs')
        return self._core.decode([i-OFFSET for i in ids],skip_special_tokens=False)

    def serialize(self,messages,objective='assistant',max_length=None):
        if objective not in ('assistant','all'):raise ValueError('Unknown loss objective')
        if not messages:raise ValueError('Nonempty conversation required')
        ids,mask=[STRUCTURAL['bos']],[0]
        for message in messages:
            if not isinstance(message,dict) or set(message)!={'role','content'}:
                raise ValueError('Only role/content messages supported; structured tool calls need a dedicated serializer')
            role=message.get('role');content=message.get('content')
            if role not in ROLES or not isinstance(content,str):raise ValueError('Invalid role/content')
            payload=self.encode(content);supervised=int(role=='assistant')
            ids.extend([STRUCTURAL[role],*payload,STRUCTURAL['message_end']])
            mask.extend([0,*([supervised]*len(payload)),supervised])
        ids.append(STRUCTURAL['eos']);mask.append(int(messages[-1]['role']=='assistant'))
        if objective=='all':mask=[0]+[1]*(len(ids)-1)
        if max_length is not None and (type(max_length) is not int or max_length<1 or len(ids)-1>max_length):
            raise ValueError('Conversation exceeds context; refusing truncation')
        return ids[:-1],ids[1:],mask[1:]

    def save(self,destination,provenance):
        destination=Path(destination)
        if destination.exists():raise FileExistsError(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        temp=Path(tempfile.mkdtemp(prefix='.bpe-',dir=destination.parent))
        try:
            (temp/'core.json').write_text(self._core.to_str(pretty=True)+'\n')
            spec={'version':1,'kind':'byte-bpe-disjoint-ids-v1','structural_ids':STRUCTURAL,
                'content_id_offset':OFFSET,'vocab_size':self.vocab_size,'normalization':'none',
                'tokenizers_version':version('tokenizers'),'provenance':provenance,
                'files':{'core.json':sha(temp/'core.json')}}
            (temp/'manifest.json').write_text(json.dumps(spec,sort_keys=True,indent=2)+'\n')
            os.rename(temp,destination)
        except BaseException:
            shutil.rmtree(temp,ignore_errors=True);raise
        return sha(destination/'manifest.json')

    @classmethod
    def load(cls,path):
        path=Path(path);spec=json.loads((path/'manifest.json').read_text())
        if (spec['version']!=1 or spec['kind']!='byte-bpe-disjoint-ids-v1'
            or spec['structural_ids']!=STRUCTURAL or spec['content_id_offset']!=OFFSET
            or spec['normalization']!='none' or spec['tokenizers_version']!=version('tokenizers')
            or set(spec['files'])!={'core.json'}
            or {p.name for p in path.iterdir()}!={'core.json','manifest.json'}):
            raise ValueError('Unsupported tokenizer manifest')
        if sha(path/'core.json')!=spec['files']['core.json']:raise ValueError('Tokenizer checksum mismatch')
        result=cls(Tokenizer.from_file(str(path/'core.json')))
        if result.vocab_size!=spec['vocab_size']:raise ValueError('Tokenizer vocabulary mismatch')
        return result


def train_release(release,output,vocab_size,min_frequency=2,max_bytes=64*1024*1024):
    """Bounded reviewed-release candidate. Never reads packets as a text corpus."""
    release,output=Path(release),Path(output)
    if output.exists():raise FileExistsError(output)
    if type(max_bytes) is not int or max_bytes<1:raise ValueError('Positive corpus byte limit required')
    parent=sha(release/'manifest.json');texts=[];identity=[];total=0
    for example in training_examples(release):
        identity.append((example['example_id'],digest(example)))
        for message in example['messages']:
            text=message['content'];total+=len(text.encode('utf-8'))
            if total>max_bytes:raise ValueError('Corpus exceeds bounded candidate budget; no silent truncation')
            texts.append(text)
    if not texts or not total:raise ValueError('Nonempty reviewed training stream required')
    if sha(release/'manifest.json')!=parent:raise ValueError('Release changed during intake')
    bpe=train_core(texts,vocab_size,min_frequency)
    provenance={'scope':'reviewed-release candidate; not production selection/freeze',
        'release_manifest_sha256':parent,'train_record_identity_sha256':digest(identity),
        'train_examples':len(identity),'train_messages':len(texts),'utf8_bytes':total,
        'requested_vocab_size':vocab_size,'target_vocab_reached':bpe.vocab_size==vocab_size,
        'min_frequency':min_frequency,'max_bytes':max_bytes}
    fingerprint=bpe.save(output,provenance)
    return {'tokenizer_manifest_sha256':fingerprint,'actual_vocab_size':bpe.vocab_size,**provenance}


def validate_slices(slices):
    if not isinstance(slices,dict) or not slices:
        raise ValueError('Nonempty named development slices required')
    for name,texts in slices.items():
        if (not isinstance(name,str) or not name or not isinstance(texts,(list,tuple))
            or not texts or any(not isinstance(s,str) or not s for s in texts)):
            raise ValueError('Each development slice requires a nonempty list of strings')


def measure(bpe,slices,architecture=None):
    """Development slices only; never feed them to candidate training."""
    validate_slices(slices)
    result={}
    for name,texts in sorted(slices.items()):
        if not texts:raise ValueError('Nonempty evaluation slice required')
        lengths=[len(bpe.encode(s)) for s in texts];chars=sum(map(len,texts));bytes_=sum(len(s.encode('utf-8')) for s in texts)
        if not chars:raise ValueError('Nonempty evaluation text required')
        if any(bpe.decode(bpe.encode(s))!=s for s in texts):raise AssertionError('Text round-trip failed')
        result[name]={'examples':len(texts),'utf8_bytes':bytes_,'characters':chars,'tokens':sum(lengths),
            'tokens_per_character':sum(lengths)/chars,'tokens_per_utf8_byte':sum(lengths)/bytes_,
            'max_content_tokens':max(lengths),
            'max_single_user_message_positions':max(len(bpe.serialize([{'role':'user','content':s}])[0]) for s in texts),
            'slice_sha256':digest(texts)}
    config=architecture or Config(hidden_size=512,intermediate_size=1536,num_layers=24,num_heads=8,num_kv_heads=2,max_seq_len=2048)
    c=replace(config,vocab_size=bpe.vocab_size)
    return {'actual_vocab_size':bpe.vocab_size,'parameters_at_actual_vocab':c.parameter_count,
        'fp32_weight_bytes':c.parameter_count*4,'slices':result,
        'scope':'Development token efficiency/round-trip; no perplexity or conversation-quality claim'}


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    p.add_argument('--vocab-size',type=int,required=True);p.add_argument('--min-frequency',type=int,default=2)
    p.add_argument('--max-bytes',type=int,default=64*1024*1024)
    a=p.parse_args();print(json.dumps(train_release(a.release,a.output,a.vocab_size,a.min_frequency,a.max_bytes),indent=2))


if __name__=='__main__':main()
