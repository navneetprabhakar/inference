import hashlib,io,json,sqlite3,tarfile,tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote
import render_shard as rs
import reader_core as rc
HERE=Path(__file__).resolve().parent
def fixture(page):
    title='Fixture Book/Chapter '+str(page)
    return {'name':title,'identifier':page,'url':'https://en.wikibooks.org/wiki/'+quote(title.replace(' ','_'),safe='/'),'namespace':{'identifier':0},'is_part_of':{'identifier':'enwikibooks'},'version':{'identifier':page+100},'license':[{'identifier':'CC-BY-SA-4.0','url':'https://creativecommons.org/licenses/by-sa/4.0/'}],'article_body':{'html':'<nav class="navbox"><span class="toc">Remove</span></nav><p>'+('Onl<span>in</span>e is a useful source of information. '*8)+'</p><pre><span>let</span> x = 1;\nprint(x)</pre>','wikitext':'Fixture source'}}

def main():
 checks=[]
 with tempfile.TemporaryDirectory(dir=HERE) as td:
  p=Path(td);records=[fixture(i) for i in [1,2,3]];payloads=[(json.dumps(r)+'\n').encode() for r in records];archive=p/'fixture.tar.gz'
  with tarfile.open(archive,'w:gz',format=tarfile.USTAR_FORMAT) as t:
   b=b''.join(payloads);m=tarfile.TarInfo('fixture.ndjson');m.size=len(b);t.addfile(m,io.BytesIO(b))
  manifest=p/'canonical.sqlite3';d=sqlite3.connect(manifest);d.execute('create table candidates(source_ordinal integer primary key,data text)')
  for n,r in enumerate(records,1):
   c=rc.core.extract_record(r);candidate={'source_ordinal':n,'page_id':r['identifier'],'revision_id':r['version']['identifier'],'title':r['name'],'url':r['url'],'html_sha256':c['html_sha256'],'wikitext_sha256':c['wikitext_sha256'],'family_id':'canonical:joined-family','license_original_metadata':r['license'],'record_sha256':rc.digest(payloads[n-1]),'member_ordinal':1,'line':n}
   d.execute('insert into candidates values (?,?)',(n,json.dumps(candidate)))
  d.commit();d.close();mh=rc.file_sha(manifest);job={'ordinals':[2,3],'end_source_ordinal':3,'rows':[{'source_ordinal':i,'record_sha256':rc.digest(payloads[i-1])} for i in [2,3]]};profile={'canonical_path':manifest,'canonical_sha256':mh,'jobs_loaded':[job]*8}
  with patch.object(rc,'ARCHIVE_SHA256',rc.file_sha(archive)),patch.object(rs.effective_profile,'load',return_value=profile):
   for shard in [1,8]:
    out=p/('render-'+str(shard));out.mkdir();result=rs.render(archive,out,shard,rc.shared_clock(),production=False)
    assert result['status']=='COMPLETE_CANONICAL_RENDER_SHARD_NO_ADMISSION';checks.append('bounded_residual_worker_'+str(shard))
    db=sqlite3.connect(out/'rendered.sqlite3');rows=[(i,json.loads(x)) for i,x in db.execute('select source_ordinal,data from rendered order by source_ordinal')];assert [i for i,_ in rows]==[2,3];checks.append('old_ordinal_not_rendered_'+str(shard))
    assert all('Online' in r['text'] and 'let x = 1;\nprint(x)' in r['text'] and r['family_id']=='canonical:joined-family' and r['training_admitted'] is False for _,r in rows);checks.append('fixed_renderer_family_provenance_'+str(shard))
    for i,r in rows:
     for start,end,h in db.execute('select start,end,hash from blocks where source_ordinal=?',(i,)):assert rc.digest(r['text'][start:end].encode())==h
    assert bool(result['stats']['gzip_eof_crc_verified'])==(shard==8);checks.append('prefix_vs_complete_EOF_distinction_'+str(shard));db.close()
    assert len(result['stats']['slowest_records'])==2 and result['stats']['timings']['extraction_total_seconds']>0;checks.append('bounded_measured_timing_'+str(shard))
 print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
if __name__=='__main__':main()
