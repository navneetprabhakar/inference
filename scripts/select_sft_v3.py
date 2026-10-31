"""Predeclared dev-only ranking. A winner failing guards is diagnostic, not promoted."""
POLICY={'primary':'0.4 single + 0.25 chain + 0.2 result + 0.15 accepted clarification','guards':'grounding, no-tool abstention and error no more than 5 percentage points below starting checkpoint; each retention PPL <=105% of starting checkpoint','tie_break':'lower chat repetition, then earlier milestone, then lower LR','fresh_test':'One frozen release: selected candidate and both existing references; no subsequent selection/tuning on test.'}
def rank(report,baseline):
 m=report['metrics'];b=baseline['metrics']
 value=.4*m['single']['strict_success_fraction']+.25*m['chain']['strict_success_fraction']+.2*m['result']['strict_success_fraction']+.15*m['clarify']['accepted_missing_slot_fraction']
 guards={'grounded':m['grounded']['strict_success_fraction']>=b['grounded']['strict_success_fraction']-.05,'abstention':m['none']['tool_abstention_fraction']>=b['none']['tool_abstention_fraction']-.05,'error':m['error']['strict_success_fraction']>=b['error']['strict_success_fraction']-.05}
 for name,ret in report['language_retention'].items():guards[name]=ret['perplexity']<=1.05*baseline['language_retention'][name]['perplexity']
 return {'score':value,'guards':guards,'eligible':all(guards.values()),'chat_repetition':m['chat']['mean_repeated_4gram_fraction']}
