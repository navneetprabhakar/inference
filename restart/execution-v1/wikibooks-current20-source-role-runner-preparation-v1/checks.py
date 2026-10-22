"""Actual original-pipeline instrumentation on synthetic HTML only."""
import copy,json,pathlib,sys,tempfile
import inventory
def run():
 cases=[]
 def no(name,fn):
  try:fn()
  except (ValueError,KeyError):cases.append(name);return
  raise AssertionError(name)
 extractor,renderer,policy,deps=inventory.dependencies()
 def fixture(html):return {'identifier':7,'name':'Synthetic Page','url':'https://en.wikibooks.org/wiki/Synthetic_Page','version':{'identifier':9},'article_body':{'html':html,'wikitext':'synthetic'},'license':[{'url':'https://creativecommons.org/licenses/by-sa/4.0/'}]}
 for label,html in [('short_definition','<p>A complete short definition.</p>'),('code_with_explanation','<p>This code prints a value.</p><pre>x = 1\nprint(x)</pre>'),('reference_list','<p>Other works include:</p><ul><li><a href="./Work">A work</a></li></ul>'),('instruction_links','<ol><li>Read the <a href="./Instructions">instructions</a> first.</li></ol>'),('historical_date','<p>As of 2004, this example used a historical technology.</p>')]:
  native=fixture(html);before=json.dumps(native,sort_keys=True);baseline=extractor.extract_record(native);blocks=inventory.blocks_for(baseline);original=renderer.render_blocks;result,roles=inventory.instrument(native,baseline['text'],blocks,extractor,renderer,policy,[])
  assert before==json.dumps(native,sort_keys=True) and renderer.render_blocks is original and result['text']==baseline['text'] and not roles['text_changed'] and roles['source_nodes_removed']==0;assert all(b['role']!='verified_site_disclaimer_component' for b in roles['blocks']);cases.append('actual_original_pipeline_'+label+'_no_text_or_node_changes')
  if label=='code_with_explanation':assert any(b['kind']=='pre' for b in roles['blocks'])
  if label=='reference_list':assert roles['blocks'][-1]['link_only_candidate_diagnostic'] and roles['blocks'][-1]['role']=='subject_or_reference_candidate'
  if label=='instruction_links':assert not roles['blocks'][-1]['link_only_candidate_diagnostic']
 native=fixture('<p>Unchanged body.</p>');baseline=extractor.extract_record(native);blocks=inventory.blocks_for(baseline);original=renderer.render_blocks
 no('whole_text_mismatch_held_not_rewritten',lambda:inventory.instrument(native,'WRONG',blocks,extractor,renderer,policy,[]));assert renderer.render_blocks is original
 bad=copy.deepcopy(blocks);bad[0]['hash']='0'*64;no('original_block_hash_mismatch_held',lambda:inventory.instrument(native,baseline['text'],bad,extractor,renderer,policy,[]));assert renderer.render_blocks is original
 class NoCall:
  def extract_record(self,native):return baseline
 no('missing_original_renderer_hook_refused',lambda:inventory.instrument(native,baseline['text'],blocks,NoCall(),renderer,policy,[]))
 text='Header\n\nMain prose\n\nNavigation';raw=text.encode();end=text.index('\n\nMain');side={'source_ordinal':7,'source_SHA256':inventory.digest(raw),'partition':[{'role':'presentation','source_UTF8_range':[0,end],'SHA256':inventory.digest(raw[:end]),'text':text[:end]}]};span=inventory.manual_annotations(text,[{'ordinal':0,'start':0,'end':end}],side,7);assert span[0]['wholly_contained_block_ordinals']==[0];cases.append('finite_manual_sidecar_annotation_no_generalized_deletion')
 no('samewords_wrong_source_identity_not_manual_override',lambda:inventory.manual_annotations(text,blocks,side,8));no('changed_fullparent_text_not_manual_override',lambda:inventory.manual_annotations(text+'x',blocks,side,7))
 with tempfile.TemporaryDirectory(prefix='WBrole-runner-fixture-') as t:
  out=pathlib.Path(t)/'child';code="import pathlib,json,sys;p=pathlib.Path(sys.argv[1])/'result.json';b=json.dumps({'status':'COMPLETE_SYNTHETIC'}).encode();p.write_bytes(b+b' '*(32768-len(b)))";inventory.supervisor.supervise(out,lambda start:[sys.executable,'-B','-c',code,str(out)]);assert json.loads((out/'supervisor.json').read_text())['child_reaped'];cases.append('actual_copied_supervisor_synthetic_child_ownership_reap')
 return {'status':'PASS_SYNTHETIC_ONLY','controls':len(cases),'cases':cases,'actual_dependency_origins':deps,'retained_source_DOM_applications':0}
if __name__=='__main__':print(json.dumps(run(),indent=2))
