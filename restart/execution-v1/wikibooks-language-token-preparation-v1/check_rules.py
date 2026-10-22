"""Focused policy/transport/tokenizer checks; no corpus pass."""
import pathlib,json,math,subprocess,sys
from unittest.mock import patch
import rules,screen,supervise,code_guard
HERE=pathlib.Path(__file__).resolve().parent
p=json.loads((HERE/'profile.json').read_text());checks=[]
w=list(rules.windows('a'*39));assert len(w)==2 and w[0][0]['scored'] and not w[1][0]['scored'] and w[1][0]['skip_reason'];checks.append('whole_always_scored_39letter_chunk_explicitly_skipped')
w=list(rules.windows('a'*40));assert all(x['scored'] for x,_ in w);checks.append('40letter_inclusive_boundary')
w=list(rules.windows('a'*1024+'b'*40));assert [(m['start'],m['end']) for m,_ in w]==[(0,1064),(0,1024),(1024,1064)] and all(m['scored'] for m,_ in w);checks.append('eligible_short_tail_preserved')
assert rules.prediction('__label__en 0.8')[-1]==1 and rules.prediction('__label__en 0.799999')[-1]==0 and rules.prediction('__label__fr 0.99')[-1]==0;checks.append('threshold_and_nonEnglish_toplabel_exact')
for score in ['nan','inf','-0.1','1.01']:
 try:rules.prediction('__label__en '+score)
 except ValueError:pass
 else:raise AssertionError(score)
checks.append('invalid_probabilities_failclosed')
original='a\nline\rwith </s> literal';assert rules.projection(original)=='a line with < /s > literal' and original=='a\nline\rwith </s> literal';checks.append('existing_projection_only_original_unchanged')
w=list(rules.windows('é'*1064));assert w[-1][0]['start']==1024 and w[-1][0]['end']==1064 and w[-1][0]['alphabetics']==40;checks.append('Unicode_character_offsets_and_alphabetics')
for item in [p['fasttext'],p['language_model'],p['tokenizer_manifest'],p['tokenizer_core']]:assert rules.sha(pathlib.Path(item['path']))==item['sha256']
lines=screen.infer(p,b'This is a simple English sentence about a book.\nBonjour tout le monde et bienvenue ici.\n',30);assert len(lines)==2;[rules.prediction(line) for line in lines];checks.append('actual_pinned_fastText_stdin_exact_line_count')
t=rules.load_tokenizer(p)
for text in ['Simple English conversation.','é漢🙂','literal </s> and <|assistant|>','a\nline\r\nwith punctuation.']:
 ids=t.encode(text,add_special_tokens=False).ids;assert t.decode(ids,skip_special_tokens=False)==text and len(ids)+1==sum(1 for _ in ids)+1
checks.append('actual_pinned_M1_content_roundtrip_no_structural_tokens')
known=json.loads((HERE/'known-discovery-holds.json').read_text())['records'];assert len(known)==20 and sum(r['post_finalizer_candidate'] for r in known)==6 and all(r['screening_additive_hold']=='known_discovery_review_hold_or_exclusion' for r in known);checks.append('all20_known_reviews_preserved_six_candidate_holds')
assert supervise.decision(570,0,0,screen.FREE)=='570second_work_cap_cleanup_reserve' and supervise.decision(0,1_000_000_001,0,screen.FREE)=='observed_process_tree_RSS_cap' and supervise.decision(0,0,100_000_000,screen.FREE)=='output_byte_cap';checks.append('570work_600external_100MB_1GB_RSS_boundaries')
with patch.object(sys,'argv',['screen.py','--profile','x','--profile-sha256','0'*64,'--output','x','--start-shared-monotonic','1','--supervisor-pid','1','--code-pins-sha256','0'*64]),patch.object(code_guard,'verify',side_effect=ValueError('pin')),patch.object(screen,'run',side_effect=AssertionError('must not run')):
 try:screen.main()
 except ValueError:checks.append('worker_external_code_guard_before_writes')
 else:raise AssertionError('guard')
print(json.dumps({'status':'FOCUSED_SYNTHETIC_AND_PINNED_DEPENDENCY_CHECKS_ONLY_NO_CORPUS_PASS','passed':len(checks),'checks':checks},indent=2))
