from pathlib import Path
import tempfile,subprocess
O=Path(__file__).resolve().parent
protected=' '.join('word'+str(i) for i in range(100));a=' '.join(protected.split()[16:48]);short='too short for a global exclusion';full='these are twelve clearly distinct words in a protected complete example sentence'
texts=['unrelated text', 'prefix '+a+' suffix',full,short,protected.replace('word33','altered')]
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'p').write_text('100\t'+protected+'\n101\t'+full+'\n102\t'+short+'\n');(p/'i').write_text('\n'.join(texts)+'\n')
 subprocess.run([str(O/'containment'),str(p/'p'),str(p/'i'),str(p/'o')],check=True,capture_output=True)
 hits={int(x.split('\t')[0]) for x in (p/'o').read_text().splitlines()}
 assert hits=={2,3,5},hits
print('PASS containment: full text, embedded span, changed document and short/common-phrase controls')
