"""Synthetic lexical closure and encoding checks; no source or GPU access."""
from pack_train_v1 import components,encode
h=lambda body:[dict(role='user',content='Hi'),dict(role='assistant',content='Hello'),dict(role='user',content=body),dict(role='assistant',content='The requested details are included above.')]
a=h(' '.join('word'+str(i) for i in range(50)));b=h(' '.join('word'+str(i) for i in range(49))+' replacement');c=h('A completely unrelated topic about birds trees rivers violet lamps purple stars.');d=[dict(x,content=x['content'].upper()) for x in a]
g,text,edges=components({'a':a,'b':b,'c':c,'d':d})
assert g['a']==g['b']==g['d']=='a' and g['c']=='c'
assert text['a']==text['d'] and text['a']!=text['b']
quarantined={g['b']};assert {i for i in g if g[i] in quarantined}=={'a','b','d'}
assert any(e['kind']=='exact' for e in edges) and any(e['kind']=='strong_lexical' for e in edges)
assert encode([0,50256,-100])==b'\x00\x00\x50\xc4\xff\xff'
try:encode([65535])
except ValueError:pass
else:raise AssertionError('raw sentinel must not be input token')
print('6 lexical closure/dedup/encoding fixtures PASS; no corpus read')
