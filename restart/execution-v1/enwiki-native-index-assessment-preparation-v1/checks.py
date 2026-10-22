import core,bz2,hashlib,io,json
checks=[]
def case(name,encoded,valid=True,limits=None):
 c=dict(core.CAPS);c.update(sample_rows=2)
 if limits:c.update(limits)
 try:r=core.assess(io.BytesIO(encoded),hashlib.sha256(encoded).hexdigest(),hashlib.md5(encoded).hexdigest(),hashlib.sha1(encoded).hexdigest(),len(encoded),1000,'0'*64,c)
 except (ValueError,OSError,EOFError,UnicodeError):
  if valid:raise
  checks.append(name+'_refused');return
 if not valid:raise AssertionError(name)
 checks.append(name+'_pass');return r
raw=b'0:1:A: colon intact\n0:1:Duplicate ID occurrence\n100:2:Third\n';encoded=bz2.compress(raw)
r=case('colon_duplicateIDs_nextoffset_lastXMLbound',encoded);assert r['stats']['rows']==3 and r['stats']['offset_groups']==2 and not r['global_page_ID_uniqueness_proven'];assert all(x['compressed_XML_block_end_exclusive']==(100 if x['compressed_XML_block_start']==0 else 1000) for x in r['samples'])
# Lowest hashes independently reconstructed over all THREE rows, preserving exactnewlinehashes.
allrows=[core.parse(x,i,1000) for i,x in enumerate(raw.splitlines(keepends=True),1)];prior=lambda row:hashlib.sha256(('enwiki-native-index-row-discovery-v1\n'+'0'*64+'\n'+hashlib.sha256(encoded).hexdigest()+'\n'+str(row['row_ordinal'])).encode()).hexdigest();expected=sorted(allrows,key=lambda row:(prior(row),row['row_ordinal']))[:2];assert [x['row_ordinal'] for x in r['samples']]==[x['row_ordinal'] for x in expected];checks.append('sample_exact_lowest_seed_source_ordinal_hashes')
assert core.parse(b'0:1:A: B\n',1,1000)['title_observed']=='A: B';checks.append('colon_title_and_newline_hash_exact')
case('empty_compressed',b'',False);case('empty_valid_bzip2_index',bz2.compress(b''),False);case('truncated',encoded[:-3],False)
bad=bytearray(encoded);bad[-6]^=128;case('CRC_corrupt',bytes(bad),False)
case('trailing_junk',encoded+b'junk',False);case('concatenated_BZ2_members',bz2.compress(b'0:1:A\n')+bz2.compress(b'10:2:B\n'))
case('decreasingoffset',bz2.compress(b'10:1:A\n0:2:B\n'),False);case('linebound',encoded,False,{'line_bytes':10});case('decodedbound',encoded,False,{'decoded_bytes':10});case('rowbound',encoded,False,{'rows':2});case('groupbound',encoded,False,{'group_rows':1});case('groupbytebound',encoded,False,{'group_raw_bytes':5})
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_NO_INDEX_DECODE','count':len(checks),'checks':checks,'actual_index_decompressions':0,'network_requests':0},indent=2))
