"""Tiny in-memory index fixtures only, no retained database read."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import freeze as f


def fixture():
    db=sqlite3.connect(':memory:')
    db.executescript('CREATE TABLE groups(group_ordinal INTEGER PRIMARY KEY,block_start,block_end_exclusive,first_row,last_row,row_count); CREATE TABLE rows(row_ordinal INTEGER PRIMARY KEY,page_id,group_ordinal,title,raw_line_sha256,raw_line_bytes,line_ends_LF,noncanonical_offset_ascii,noncanonical_page_ascii);')
    db.executemany('INSERT INTO groups VALUES (?,?,?,?,?,?)',[(1,570,1000,1,2,2),(2,1000,1500,3,3,1),(3,1500,2000,4,4,1)])
    rawlines=['00570:0001:Title: café 雪\n','570:2:Code/reference intro\n','1000:3:Short definition']
    for i,raw in enumerate(rawlines,1):
        a,b,title=raw.removesuffix('\n').split(':',2);group=1 if i<3 else 2;rb=raw.encode()
        db.execute('INSERT INTO rows VALUES (?,?,?,?,?,?,?,?,?)',(i,int(b),group,title,hashlib.sha256(rb).digest(),len(rb),int(raw.endswith('\n')),a if a!=str(int(a)) else None,b if b!=str(int(b)) else None))
    db.commit()
    return db,rawlines


def run():
    cases=[];target={'groups':2,'rows':3,'header_bytes':570,'end_exclusive':1500,'maximum_group_bytes':500}
    def bad(name,action):
        try:action()
        except (ValueError,OSError):cases.append(name)
        else:raise AssertionError(name)
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);db,raw=fixture();out=root/'valid';out.mkdir()
        r=f.freeze(db,out,target)
        records=[json.loads(line) for line in (out/'rows.jsonl').read_text().splitlines()]
        assert [x[-1] for x in records]==raw and records[0][3]=='Title: café 雪'
        assert records[0][2]==1 and records[0][0]==1 and records[0][1]==1
        assert r['rows']==3 and r['all_raw_line_hashes_reconstructed_exact'] and r['next_group_boundary_not_selected']=={'group_ordinal':3,'compressed_start':1500,'first_row_ordinal':4}
        assert r['row_manifest_SHA256']==f.sha(out/'rows.jsonl')
        cases+=['exact_onebased_rows_groups_titles_numeric_lexemes_LF_and_rawline_roundtrip','all_row_hashes_reconstructed_exact','next_group_boundary_not_added_to_selection','streamed_manifest_digest']
        db.close()
        changes=[
            ('noncontiguous_group_offsets','UPDATE groups SET block_start=1001 WHERE group_ordinal=2'),
            ('wrong_group_row_interval','UPDATE groups SET first_row=2 WHERE group_ordinal=2'),
            ('missing_selected_row','DELETE FROM rows WHERE row_ordinal=2'),
            ('row_group_mismatch','UPDATE rows SET group_ordinal=2 WHERE row_ordinal=1'),
            ('rawline_hash_mismatch',"UPDATE rows SET title='changed' WHERE row_ordinal=1"),
            ('wrong_next_group_boundary','UPDATE groups SET block_start=1501 WHERE group_ordinal=3'),
            ('missing_next_group_boundary','DELETE FROM groups WHERE group_ordinal=3')]
        for name,sql in changes:
            db,_=fixture();db.execute(sql);out=root/name;out.mkdir()
            bad(name,lambda:f.freeze(db,out,target));db.close()
        db,_=fixture();out=root/'wrongtarget';out.mkdir()
        bad('finite_target_no_resizing_or_replacement',lambda:f.freeze(db,out,{**target,'rows':4}));db.close()
    return {'status':'PASS_SYNTHETIC_INDEX_METADATA_ONLY','controls':len(cases),'cases':cases}


if __name__=='__main__':print(json.dumps(run(),indent=2))
