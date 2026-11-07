"""Author-owned grounded state programs, independent of prose renderer.
Verifier must check prompt entailment/response support independently; these programs
are candidate evidence, never their own independent verification.
"""
SPECS={}
def spec(key,facts,queries,events=None,formats=None):
 SPECS[key]={'initial_facts':facts,'turn_events':events or [{},{}], 'queries':queries,'formats':formats or ['sentence','sentence']}
def a(g,s,f,q,e=None,fmt=None):spec(g+'/'+s,f,q,e,fmt)
G='fulfillment'
a(G,'service-notice',{'kiln':'{place} pottery kiln','status':'unavailable','cause':'maintenance','collection':'finished pieces','collector':'{person}'},[['kiln','status','cause','collection','collector'],['collection','collector','kiln','status','cause']])
a(G,'volunteer-invitation',{'activity':'sort donated fabric','location':'{place}','contact':'{person}'},[['activity','location','contact']]*2,fmt=['friendly invitation; no schedule','formal invitation; no schedule'])
a(G,'equipment-reminder',{'recipient':'{person}','objects':['compass','case'],'destination':'{place}'},[['recipient','objects','destination']]*2,fmt=['reminder','case before compass'])
a(G,'safe-order',{'sequence':['fasten empty stand','place sign'],'holder':'{person}'},[['sequence','holder'],['sequence']])
a(G,'availability-update',{'ready':'{item}','stage':'inspection','location':'{place}','unready':'{thing}','remaining':'assembly'},[['ready','stage','location','unready','remaining']]*2)
a(G,'polite-decline',{'object':'{item}','decision':'cannot lend','reason':'reserved for a demonstration'},[['object','decision','reason']]*2,fmt=['courteous decline','no apology'])
a(G,'grounded-explanation',{'protected':'{item}','other':'{thing}','mechanism':'padded sleeve','effect':'prevents rubbing during transport'},[['protected','other','mechanism','effect'],['effect']])
a(G,'two-stage-plan',{'object':'{item}','sequence':['inspect seams','put in clean sleeve']},[['object','sequence']]*2)
a(G,'grounded-apology',{'object':'{item}','status':'repair delayed','reason':'replacement part has not arrived','estimate':None},[['object','status','reason','estimate']]*2,fmt=['apology','no apology'])
a(G,'question-draft',{'addressee':'{person}','location':'{place}','policy':None,'subject':'donated musical instruments'},[['addressee','location','subject','policy']]*2,fmt=['question','conditional follow-up question'])
a(G,'thank-you',{'person':'{person}','action':'repairing latch','object':'{item}'},[['person','action','object']]*2,fmt=['thanks','warmer thanks'])
G='facts'
a(G,'storage',{'first':'{item}','first_location':'{place}','second':'{thing}','second_location':'{alternate}'},[['first','first_location'],['second','second_location']])
a(G,'responsibilities',{'arrivals':'{person}','departures':'{other}','location':'{place}'},[['departures','location'],['arrivals','location']])
a(G,'material-record',{'first':'{item}','first_padding':'cotton','second':'{thing}','second_padding':'felt'},[['second','second_padding'],['first','first_padding','second','second_padding']])
a(G,'permission-record',{'object':'{item}','inspect':'{person}','remove':'{other}','location':'{place}','exclusive_remove':True},[['remove','object','location'],['inspect','remove','exclusive_remove']])
a(G,'route-order',{'route':['{place}','{alternate}','{third}']},[['route[1]'],['route[2]']])
a(G,'membership',{'stitching':['{person}','{other}'],'transport':'{thirdperson}','stitching_complete':True},[['transport','stitching','stitching_complete'],['stitching']])
a(G,'exception',{'exempt':'{item}','ordinary':'{thing}','rule':'seal required'},[['exempt'],['ordinary','rule']])
a(G,'capacity-record',{'first':'{item}','first_capacity':'{n}','second':'{thing}','second_capacity':'{m}'},[['first','first_capacity'],['second','second_capacity']])
a(G,'ownership',{'owner':'{person}','custodian':'{other}','object':'{item}','ownership_transferred':False},[['owner','custodian','object'],['owner','ownership_transferred']])
a(G,'access-condition',{'badge_location':'{place}','reservation_location':'{alternate}'},[['reservation_location'],['badge_location']])
a(G,'source-conflict',{'object':'{item}','original':'{place}','amended':'{alternate}','authority':'amended'},[['amended','authority'],['original']])
G='corrections'
a(G,'destination-change',{'object':'{item}','destination':'{place}'},[['object','destination']]*2,[{}, {'set':{'destination':'{alternate}'}}])
a(G,'custodian-change',{'object':'{item}','custodian':'{person}'},[['object','custodian']]*2,[{}, {'set':{'custodian':'{other}'}}])
a(G,'quantity-amendment',{'object':'{item}','identifier':'{n}'},[['object','identifier']]*2,[{}, {'set':{'identifier':'{m}'}}])
a(G,'remove-member',{'participants':['{person}','{other}','{thirdperson}']},[['participants']]*2,[{}, {'remove':{'participants':'{other}'}}])
a(G,'add-member',{'object':'{item}','inspectors':['{person}']},[['object','inspectors']]*2,[{}, {'append':{'inspectors':'{other}'}}])
a(G,'permission-revoke',{'person':'{person}','object':'{item}','may_move':True},[['person','object','may_move']]*2,[{}, {'set':{'may_move':False}}])
a(G,'rename-object',{'rack_name':'{item}'},[['rack_name']]*2,[{}, {'set':{'rack_name':'{thing}'}}])
a(G,'swap-roles',{'packing':'{person}','loading':'{other}'},[['packing','loading']]*2,[{}, {'swap':['packing','loading']}])
a(G,'retract-change',{'object':'{item}','destination':'{place}','draft_destination':'{alternate}','draft_status':'unapproved'},[['destination','draft_status']]*2,[{}, {'set':{'draft_status':'cancelled'}}])
a(G,'selective-update',{'first':'{person}','first_location':'{place}','second':'{other}','second_location':'{alternate}'},[['first','first_location','second','second_location']]*2,[{}, {'set':{'second_location':'{third}'}}])
a(G,'status-change',{'object':'{item}','inspection':'awaiting','packing':None},[['object','inspection'],['object','inspection','packing']],[{}, {'set':{'inspection':'complete','packing':'not started'}}])
G='transformations'
a(G,'condense-notice',{'agent':'{person}','object':'{item}','location':'{place}','action':'inspect','tense':'future'},[['agent','object','location','action','tense']]*2,fmt=['short active','passive object subject'])
a(G,'polite-request',{'object':'{item}','destination':'{place}','notify':'{person}','sequence':['bring','notify arrival']},[['object','destination','notify','sequence']]*2,fmt=['courteous request','direct request'])
a(G,'combine-facts',{'object':'{item}','prepared':'{person}','checked':'{other}'},[['prepared','object','checked'],['checked','object','prepared']],fmt=['one sentence','reversed clauses'])
a(G,'active-voice',{'agent':'{person}','object':'{item}','location':'{place}','action':'repair','tense':'past'},[['agent','object','location','action','tense']]*2,fmt=['active','passive'])
a(G,'separate-actions',{'collector':'{person}','object':'{item}','location':'{place}','inspector':'{other}'},[['collector','object','location','inspector']]*2,fmt=['two sentences','semicolon'])
a(G,'remove-duplication',{'object':'{item}','ready':True,'collector':'{person}','location':'{place}'},[['object','ready','collector','location']]*2,fmt=['deduplicated','one sentence'])
a(G,'plain-language',{'agent':'{person}','object':'{item}','destination':'{place}','condition':'permission received','permission_received':None},[['agent','object','destination','condition'],['condition','permission_received']])
a(G,'positive-negative',{'object':'{item}','available':False,'inspector':'{person}'},[['object','available','inspector'],['object','inspector']],fmt=['no phrase not available','reason only'])
a(G,'third-person',{'agent':'{person}','object':'{item}','destination':'{place}','action':'bring','tense':'future'},[['agent','object','destination','action','tense']]*2,[{}, {'set':{'tense':'past'}}],['name not pronoun','completed action grammar only'])
a(G,'headline',{'object':'{item}','inspection':'passed','collection':'ready','location':'{place}'},[['object','collection','location'],['object','inspection','collection','location']],fmt=['heading','complete sentence'])
a(G,'quote-content',{'requester':'{person}','moved':'{item}','reference':'{thing}','relation':'beside'},[['requester','moved','reference','relation'],['moved','reference','relation']])
G='clarification'
a(G,'missing-destination',{'object':'{item}','destination':None},[['destination'],['object','destination']],[{}, {'set':{'destination':'{place}'}}],['ask missing destination','dispatch draft'])
a(G,'missing-recipient',{'object':'{item}','recipient':None,'location':None},[['recipient'],['recipient','object','location']],[{}, {'set':{'recipient':'{person}','location':'{place}'}}],['ask recipient','invitation draft'])
a(G,'ambiguous-object',{'options':['{item}','{thing}'],'object':None,'inspector':None},[['options','object'],['object','inspector']],[{}, {'set':{'object':'{thing}','inspector':'{person}'}}],['ask which object','request draft'])
a(G,'missing-reason',{'object':'{item}','reason':None},[['object','reason']]*2,[{}, {'set':{'reason':'waiting for a replacement hinge'}}],['ask reason','explanation'])
a(G,'unknown-contact',{'object':'{item}','responsible':None},[['object','responsible']]*2,[{}, {'set':{'responsible':'{person}'}}],['ask record','grounded answer'])
a(G,'unspecified-choice',{'first':'{item}','second':'{thing}','first_weight':None,'second_weight':None,'criterion':None},[['criterion'],['first','first_weight','criterion']],[{}, {'set':{'first_weight':'lightweight','second_weight':'heavy','criterion':'lightweight'}}],['ask differences and needs','select matching option'])
a(G,'missing-sequence',{'object':'{item}','steps':None},[['object','steps']]*2,[{}, {'set':{'steps':['attach base','secure handle']}}],['ask supplied steps','ordered instruction'])
a(G,'unknown-status',{'object':'{item}','inspection':None},[['object','inspection']]*2,[{}, {'set':{'inspection':'passed'}}],['ask result','grounded status'])
a(G,'unspecified-object-action',{'object':None,'destination':'{place}'},[['object','destination']]*2,[{}, {'set':{'object':'borrowed projector'}}],['ask object','return reminder'])
a(G,'ambiguous-pronoun',{'options':['{person}','{other}'],'collector':None,'object':'{item}'},[['options','collector'],['collector','object']],[{}, {'set':{'collector':'{other}'}}],['ask ambiguous referent','resolved statement'])
a(G,'missing-decision',{'object':'{item}','options':['{place}','{alternate}'],'destination':None},[['destination'],['object','destination']],[{}, {'set':{'destination':'{alternate}'}}],['ask decision','dispatch instruction'])
G='recall'
a(G,'identifier-recall',{'identifier':'{n}'},[['identifier']]*2)
a(G,'paired-recall',{'first':'{person}','first_item':'{item}','second':'{other}','second_item':'{thing}'},[['first','first_item','second','second_item'],['second','second_item','first','first_item']])
a(G,'sequential-recall',{'object':'{item}','sequence':['unpack','inspect','store']},[['sequence'],['sequence[1]']],fmt=['arrows','predecessor sentence'])
a(G,'format-recall',{'phrase':'{code}'},[['phrase']]*2,fmt=['square brackets','sentence without brackets'])
a(G,'two-item-list',{'names':['{item}','{thing}']},[['names'],['names[1]']],fmt=['slash','position sentence'])
a(G,'reason-recall',{'object':'{item}','postponed':True,'reason':'transport van needs repairs'},[['object','postponed','reason'],['reason']])
a(G,'distinguish-input',{'requested':'{n}','recorded':'{m}'},[['requested','recorded'],['requested']])
a(G,'draft-not-action',{'recipient':'{person}','object':'{item}','location':'{place}','messaging_tool':False,'sent':False},[['recipient','object','location'],['sent','messaging_tool']],fmt=['request draft','honest non-execution'])
a(G,'reason-and-place',{'object':'{item}','location':'{place}','reason':'original test bench is being repaired'},[['object','location','reason'],['location','reason']])
a(G,'quoted-identifier',{'identifier':'{n}'},[['identifier']]*2,fmt=['double quotes','complete sentence'])
a(G,'noted-limitation',{'object':'{item}','assembled':True,'inspection':None},[['object','assembled','inspection'],['assembled','inspection']])

def instantiate(surface_id,slots):
 import copy,re
 def subst(x):
  if isinstance(x,str):return x.format(**slots)
  if isinstance(x,list):return [subst(v) for v in x]
  if isinstance(x,dict):return {k:subst(v) for k,v in x.items()}
  return x
 program=subst(SPECS[surface_id]);current=copy.deepcopy(program['initial_facts']);snapshots=[]
 for event,queries in zip(program['turn_events'],program['queries']):
  current.update(event.get('set',{}))
  for key,value in event.get('remove',{}).items():current[key].remove(value)
  for key,value in event.get('append',{}).items():current[key].append(value)
  if 'swap' in event:
   first,second=event['swap'];current[first],current[second]=current[second],current[first]
  answer={}
  for key in queries:
   match=re.fullmatch(r'(.+)\[(\d+)\]',key)
   answer[key]=copy.deepcopy(current[match[1]][int(match[2])] if match else current[key])
  snapshots.append({'facts':copy.deepcopy(current),'queried_values':answer})
 return {'program':program,'snapshots':snapshots}
