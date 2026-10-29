"""Decision contract only; no training or automatic launch."""
import math
FAMILIES={'grounding','comprehension','clarification','correction','instructions','explanation'}
def fraction(n,d):
 if type(n) is not int or type(d) is not int or not 0<=n<=d or d<=0:raise ValueError('INVALID_COUNTS')
 return n/d

def readiness(m):
 for k in ['empty_correct','shuffled_correct']:fraction(m[k],120)
 if not m['measurement_valid']:return False
 if len(m['domain_correct'])!=4 or sum(m['domain_correct'])!=m['generation_correct']:raise ValueError('DOMAIN_COUNTS')
 return fraction(m['generation_correct'],60)>=.8 and all(fraction(n,15)>=11/15 for n in m['domain_correct']) and fraction(m['grounding_correct'],120)>=.8 and all(m['grounding_correct']-m[k]>=24 for k in ['empty_correct','shuffled_correct']) and fraction(m['grammar_correct'],60)>=.9

def conversation(m,final=False):
 expected=240 if final else 120
 if m['conversations']!=expected or set(m['families'])!=FAMILIES:raise ValueError('PACKET_COUNTS')
 if sum(x['total'] for x in m['families'].values())!=expected or sum(x['complete'] for x in m['families'].values())!=m['complete']:raise ValueError('FAMILY_TOTALS')
 if not 2*expected<=m['turns']<=4*expected:raise ValueError('TURN_COUNTS')
 if any(m['correct']>m[k] for k in ['language','relevant','terminal']) or any(m[k]>m['turns']-m['correct'] for k in ['unsupported','contradictions']):raise ValueError('INCONSISTENT_TURN_COUNTS')
 if not m['measurement_valid'] or not m['foundation_still_ready']:return False
 if not math.isfinite(m['native_ratio']) or not 0<m['native_ratio']<=1.25:return False
 return all(fraction(m[k],m['turns'])>=v for k,v in [('correct',.9),('language',.95),('relevant',.9),('terminal',.98)]) and fraction(m['complete'],expected)>=.8 and all(x['total']==expected//6 and fraction(x['complete'],x['total'])>=.8 for x in m['families'].values()) and fraction(m['unsupported'],m['turns'])<=.05 and fraction(m['contradictions'],m['turns'])<=.02 and 0<=m['foundation_decline']<=.05

def next_stage(stage,passed,recovery_used=False):
 if stage=='readiness':return 'conversation_screen' if passed else ('STOP_FOUNDATION' if recovery_used else 'foundation_recovery')
 if stage=='foundation_recovery':return 'conversation_screen' if passed else 'STOP_FOUNDATION'
 if stage=='conversation_screen':return 'confirmation' if passed else 'STOP_RECIPE'
 if stage=='confirmation':return 'final' if passed else 'STOP_UNCONFIRMED'
 if stage=='final':return 'BOUNDED_PILOT_PASS' if passed else 'STOP_FINAL'
 raise ValueError('UNKNOWN_STAGE')
