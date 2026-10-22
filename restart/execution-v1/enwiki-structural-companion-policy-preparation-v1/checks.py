from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent));from rules import template_rule as t,span_rule
checks=[]
def check(n,v):assert v,n;checks.append(n)
check('standalone_exactmaintenance',t('Use dmy dates',[('date','2019')],True)['prose_may_proceed_after_review'])
check('no_inline_metadata_drop',not t('Use dmy dates',[('date','2019')],False)['prose_may_proceed_after_review'])
check('unknownmaintenanceparamheld',not t('Use dmy dates',[('semantic','words')],True)['prose_may_proceed_after_review'])
check('duplicateparamsheld',not t('Use dmy dates',[('date','a'),('date','b')],True)['prose_may_proceed_after_review'])
check('shortdescriptionnotdiscarded',t('Short description',[('1','Semantic summary')],True)['class']=='semantic_page_metadata')
check('infoboxallvaluescompanion',t('Infobox settlement',[('population','174')],True)['preserve_entire_raw_node_in_companion'])
check('inlineAsOfnotdrop',t('As of',[('1','2011')],False)['action']=='HOLD_UNRESOLVED_SEMANTIC_CONTENT_NO_SILENT_DROP')
check('quoteboxnotnav',t('Quote box',[('quote','full quote')],True)['class']=='inline_or_semantic_template')
check('unknownnavnotkeywordmatched',t('Not really a Portal',[],True)['class']=='unknown_template')
check('sfnrequiresbibliography',t('sfn',[('1','Jung'),('2','2014')],False)['action']=='HOLD_UNRESOLVED_REFERENCE_SEMANTICS')
check('spanemptybrowserattrscontenttransparent',span_rule([('data-darkreader-inline-color',''),('data-darkreader-inline-bgcolor','')])['action'].startswith('PROPOSE_TRANSPARENT'))
check('spanunknownattrheld',span_rule([('onclick','anything')])['action'].startswith('HOLD'))
check('spannondisplayvalueheld',span_rule([('data-darkreader-inline-color','semantic')])['action'].startswith('HOLD'))
check('spanduplicateheld',span_rule([('data-darkreader-inline-color',''),('data-darkreader-inline-color','')])['action'].startswith('HOLD'))
check('allrulesnoactualapply',all(not t(n,[],True)['apply_to_source'] for n in ['Use dmy dates','Infobox settlement','Unknown']))
print(json.dumps({'status':'PASS_SYNTHETIC_PROPOSAL_CLASSIFIER_ONLY','checks':len(checks),'cases':checks},indent=2))
