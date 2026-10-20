# Creator: Navneet Prabhakar
import json,sqlite3
from pathlib import Path
import pytest
from slm.common.tokenizer import train_core
from slm.data.english_corpus import select,build_tokens,verify_tokens
from slm.data.schema import digest

def text(label):return ' '.join(label+str(i) for i in range(100))+'.'
def record(i,t):return dict(sid=i,example_id=str(i),parent_group_id='g'+str(i),split_group='g'+str(i),source='general',split='train',text=t,content_sha256=digest(t))
def test_component_nonapproval_and_old_heldout_precedence():
 db=sqlite3.connect(':memory:');db.execute('CREATE TABLE records(sid,data,candidate,fixed,blocked,ingredient)')
 for i in range(5):
  r=dict(candidate=True,ingredient='general',id=str(i),texts=dict(content=text('word')),tokens=150,reference={})
  db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(i,json.dumps(r),1,0,0,'general'))
 roots=[0,0,2,3,4];comp={i:dict(group_id='group'+str(i),heldout_priority=int(i==2),blocked=int(i==3)) for i in [0,2,3,4]}
 rows,ex=select(db,roots,comp,{1})
 assert [r['sid'] for r in rows]==[4]
 assert ex['direct_nonapproval_component']==2 and ex['protected_or_blocked_component']==2

def test_exact_token_stream_reconstruction_and_corruption(tmp_path):
 rows=[record(0,text('alpha')),record(1,text('beta'))];bpe=train_core([r['text'] for r in rows],300)
 tokenizer=tmp_path/'tokenizer';bpe.save(tokenizer,{'fixture':'english-corpus'})
 out=tmp_path/'tokens';result=build_tokens(rows,bpe,out,'a'*64,__import__('slm.data.stream_hash',fromlist=['sha']).sha(tokenizer/'manifest.json'),'b'*64,context=32)
 assert verify_tokens(rows,bpe,out,tokenizer)==result['processed_positions']
 rows[1]['text']+='tamper'
 with pytest.raises(ValueError,match='unchanged'):verify_tokens(rows,bpe,out,tokenizer)

def test_no_validation_or_repaired_content_admission(tmp_path):
 r=record(0,text('train'));r['split']='validation';bpe=train_core([r['text']],300)
 with pytest.raises(ValueError,match='train'):build_tokens([r],bpe,tmp_path/'x','a'*64,'b'*64,'c'*64,context=32)
