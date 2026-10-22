import sqlite3,json,tempfile,pathlib
import finalize as f
checks=[]
def case(name,rows,test):
 d=sqlite3.connect(':memory:');f.schema(d)
 for i,title,family,texts,holds in rows:
  text='\n\n'.join(texts)
  d.execute('insert into pages values (?,?,?,?,?,?,?,?,?,?,?)',(i,i,100+i,f.intern_family(d,family),title,title.count('/'),bytes.fromhex(f.digest(text.encode())),len(text),len(text.encode()),json.dumps(holds),1))
  for j,t in enumerate(texts):d.execute('insert into blocks values (?,?,?,?)',(i,j,bytes.fromhex(f.digest(t.encode())),len(t)))
 assert f.resolve(d)==len(rows);test(d);checks.append(name);d.close()
def h(d,i):return json.loads(d.execute('select holds from final_pages where source_ordinal=?',(i,)).fetchone()[0])
def expect(ok):assert ok
A='a'*80;B='b'*80;C='c'*79
case('deepest_chapter_acquires_common_alias_family_ownership',[(1,'Book/Print','alias-union',[A,B],[]),(2,'Book/Chapter/Section','alias-union',[A],[])],lambda d:expect(h(d,1)==['substantive_block_duplicates_canonical_chapter'] and h(d,2)==[]))
case('held_deep_page_cannot_own_or_clear_hold',[(1,'B/X/Y','B',[A],['math_requires_lossless_representation']),(2,'B/X','B',[A],[])],lambda d:expect(h(d,1)==['math_requires_lossless_representation'] and h(d,2)==[]))
case('79_character_block_below_threshold',[(1,'B/A','B',[C,A],[]),(2,'B/B','B',[C,B],[])],lambda d:expect(h(d,1)==h(d,2)==[]))
case('80_character_block_is_substantive',[(1,'B/A','B',[A,B],[]),(2,'B/B','B',[A,C],[])],lambda d:expect(h(d,2)==['substantive_block_duplicates_canonical_chapter']))
case('same_page_repeated_block_not_self_overlap',[(1,'B/A','B',[A,A],[])],lambda d:expect(h(d,1)==[]))
case('held_overlap_page_does_not_acquire_other_blocks',[(1,'B/A','B',[A],[]),(2,'B/B','B',[A,B],[]),(3,'B/C','B',[B],[])],lambda d:expect(h(d,2)==['substantive_block_duplicates_canonical_chapter'] and h(d,3)==[]))
case('exact_text_duplicate_across_families',[(1,'A/X','A',[A],[]),(2,'B/X','B',[A],[])],lambda d:expect(h(d,2)==['exact_text_duplicate_global'] and d.execute('select exact_owner from final_pages where source_ordinal=2').fetchone()[0]==1))
case('nonexact_cross_family_overlap_is_report_only',[(1,'A/X','A',[A,B],[]),(2,'B/X','B',[A,C],[])],lambda d:expect(h(d,1)==h(d,2)==[] and d.execute('select count(*) from cross_family_block_groups').fetchone()[0]==1))
case('held_rows_in_cross_family_report',[(1,'A/X','A',[A],['old']),(2,'B/X','B',[A],['other'])],lambda d:expect(d.execute('select occurrences,families from cross_family_block_groups').fetchone()==(2,2)))
case('binary_title_tie_order_deterministic',[(1,'B/a','B',[A],[]),(2,'B/A','B',[A],[])],lambda d:expect(h(d,1)==['exact_text_duplicate_global'] and h(d,2)==[]))
case('exact_duplicate_report_includes_held_rows',[(1,'B/A','B',[A],['old']),(2,'B/B','B',[A],[])],lambda d:expect(d.execute('select occurrences from exact_duplicate_groups').fetchone()[0]==2 and h(d,2)==[]))
assert f.holds_for({'structural_holds':['a'],'prior_v3_holds':['b']})=={'a','b'};checks.append('union_prior_holds_preserved')
assert f.holds_for({'structural_holds':[]},False)=={'excluded_by_parent_reconciled_identity_manifest'};checks.append('identity_excluded_rows_held')
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t);recipe=p/'recipe.json';recipe.write_text(json.dumps({'status':'PARENT_FROZEN_COMPLETE_RENDER_INPUTS_NO_ADMISSION','oversize_identity_reconciliation_complete':False}));out=p/'out'
 try:f.run(recipe,out)
 except RuntimeError as e:assert str(e)=='output_outside_intake'
 else:raise AssertionError('should_fail_closed')
 assert json.loads((out/'result.json').read_text())['status']=='PARTIAL_GLOBAL_RECONCILIATION_NO_ADMISSION';checks.append('failed_run_retains_bounded_terminal_receipt')
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
