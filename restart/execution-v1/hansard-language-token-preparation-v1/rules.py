"""Frozen diagnostic policy; pure functions, no fitting or text rewrite."""
import hashlib,json,math,pathlib,re
WIDTH=1024
MIN_ALPHA=40
THRESHOLD=.8

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def projection(text):
 # Exact existing slm.data.detector_projection.fasttext_line implementation.
 if not isinstance(text,str):raise ValueError('Original text required')
 return text.replace('\n',' ').replace('\r',' ').replace('</s>','< /s >')
def windows(text):
 yield {'kind':'whole','start':0,'end':len(text),'alphabetics':sum(c.isalpha() for c in text),'scored':True,'skip_reason':None},text
 for start in range(0,len(text),WIDTH):
  chunk=text[start:start+WIDTH];alpha=sum(c.isalpha() for c in chunk);scored=alpha>=MIN_ALPHA
  yield {'kind':'chunk','start':start,'end':start+len(chunk),'alphabetics':alpha,'scored':scored,'skip_reason':None if scored else 'fewer_than_40_alphabetic_characters'},chunk

def prediction(line):
 parts=line.split()
 if len(parts)!=2 or not re.fullmatch(r'__label__[a-z_\-]{2,24}',parts[0]):raise ValueError('invalid_fastText_top1_line')
 p=float(parts[1])
 if not math.isfinite(p) or not 0<=p<=1.001:raise ValueError('invalid_fastText_probability')
 english=p if parts[0]=='__label__en' else 0.
 return parts[0],parts[1],p,english,int(english>=THRESHOLD)

def load_tokenizer(profile):
 from importlib.metadata import version
 from tokenizers import Tokenizer
 m=pathlib.Path(profile['tokenizer_manifest']['path']);core=pathlib.Path(profile['tokenizer_core']['path']);manifest=json.loads(m.read_text())
 if version('tokenizers')!='0.22.2' or manifest['tokenizers_version']!='0.22.2' or manifest['content_id_offset']!=10 or manifest['vocab_size']!=8192 or manifest['normalization']!='none' or manifest['files']!={'core.json':sha(core)}:raise ValueError('M1_tokenizer_conventions_changed')
 t=Tokenizer.from_file(str(core));raw=json.loads(t.to_str())
 if any(raw[k] is not None for k in ['normalizer','post_processor','truncation','padding']) or raw['added_tokens'] or t.get_vocab_size()!=8182:raise ValueError('M1_content_count_would_transform_or_add_tokens')
 return t
