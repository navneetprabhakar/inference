"""Prospective structural deferrals and seed relation representation; no semantic scoring."""
import hashlib,re,unicodedata
VERSION='cosmopedia-explanatory-v1'
def normalize(text):return ' '.join(unicodedata.normalize('NFKC',text).lower().split())
def h(text):return hashlib.sha256(text.encode()).hexdigest()
def structural_reasons(text):
 reasons=[]
 # Line-delimited fenced blocks only; matching closer must have same character and >= opening run length.
 active=None
 for line in text.splitlines():
  m=re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$',line)
  if not m:continue
  mark,tail=m.groups()
  if active is None:active=(mark[0],len(mark))
  elif mark[0]==active[0] and len(mark)>=active[1] and not tail.strip():active=None
 if active:reasons.append('unclosed_fenced_block')
 if re.search(r'(?:\\?[_*~`|=+\-]\s*){32,}',text):reasons.append('long_symbol_run')
 if re.search(r'\[\s*(?:insert|add|provide)\s+(?:a\s+|an\s+|the\s+)?(?:link|image|video|audio|citation|reference|figure|diagram|content|text)\b[^\]\n]*\]',text,re.I):reasons.append('unresolved_insert_placeholder')
 if re.search(r'\b(?:let me know if you(?:\s+would|\x27d)? like me to continue|continue to step\s+\d+|to be continued)\b',text,re.I):reasons.append('explicit_unfinished_marker')
 lines=[line.strip() for line in text.splitlines() if line.strip()]
 if not lines:reasons.append('empty_text');return sorted(set(reasons))
 last=lines[-1]
 if re.match(r'^#{1,6}\s+\S',last):reasons.append('terminal_heading')
 # Remove closing punctuation/markdown markers; exercise blank lines and fragmentary lists may be over-deferred.
 tail=text.rstrip().rstrip(' \t\r\n\"\x27”’)]}*_`')
 if not tail or tail[-1] not in '.!?…':reasons.append('missing_terminal_sentence_punctuation')
 return sorted(set(reasons))
def seed_relation(prompt):
 m=re.match(r'^Here is an extract from a webpage:\s*\"(.*?)\"\s*\n\s*\nWrite\b',prompt,re.S)
 if m:return normalize(m.group(1)),'quoted_web_seed'
 return normalize(prompt),'full_prompt_exact_only'
def seed_shingles(seed,kind):
 if kind!='quoted_web_seed':return []
 words=re.findall(r'\w+',seed)
 if len(words)<32:return []
 # 128bit hashes; sorted unique five-word shingles, four minimum anchors.
 return sorted({hashlib.sha256(' '.join(words[i:i+5]).encode()).digest()[:16] for i in range(len(words)-4)})
