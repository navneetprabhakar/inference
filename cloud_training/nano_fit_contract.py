"""Restricted English learnability diagnostics; cannot authorize release."""
import re

def errors(contract,*,manifest,admission,train,dev,epochs,lr_multiplier,eval_interval,max_updates):
    problems=[]
    if contract.get('schema')!=1 or contract.get('objective')!='english_fit_diagnostic' or contract.get('diagnostic_only') is not True:
        return ['Explicit English diagnostic-only contract required']
    for k in ('dataset_manifest_sha256','tokenizer_sha256','required_parent_manifest_sha256','review_sha256','development_suite_sha256'):
        if not isinstance(contract.get(k),str) or not re.fullmatch('[0-9a-f]{64}',contract[k]):problems.append('Missing diagnostic hash: '+k)
    for k,actual in [('dataset_manifest_sha256',manifest['_sha256']),('tokenizer_sha256',manifest['tokenizer_sha256']),('required_parent_manifest_sha256',admission.get('parent_manifest_sha256')),('review_sha256',admission.get('review_sha256'))]:
        if contract.get(k)!=actual:problems.append('Diagnostic identity mismatch: '+k)
    if contract.get('context_tokens')!=2048 or manifest.get('context_tokens')!=2048:problems.append('Diagnostic must use native2K context')
    if manifest.get('diagnostic_only') is not True or admission.get('diagnostic_only') is not True:problems.append('Admission must prohibit production promotion')
    if train.get('sessions')!=24 or dev.get('sessions')!=12:problems.append('Exact reviewed24/12 diagnostic split required')
    if train.get('assistant_targets')!=656 or dev.get('assistant_targets')!=556:problems.append('Reviewed target mass changed')
    for split in (train,dev):
        modes=split.get('turn_modes',{})
        if modes.get('enabled_call',0) or not modes.get('enabled_no_call',0) or not modes.get('disabled_no_call',0):problems.append('English-only call abstention coverage required')
    bounds=contract.get('recipe_limits',{})
    for key,actual,hard in [('max_epochs',epochs,64),('max_pilot_updates',max_updates,64),('max_eval_interval',eval_interval,5)]:
        limit=bounds.get(key)
        if type(limit)is not int or not 1<=limit<=hard or type(actual)is not int or not 1<=actual<=limit:problems.append('Diagnostic bound invalid: '+key)
    if type(lr_multiplier) not in (int,float) or not 0<lr_multiplier<=bounds.get('max_lr_multiplier',0)<=.25:problems.append('Diagnostic learning-rate bound invalid')
    if contract.get('unresolved_required_data'):problems.append('Unresolved diagnostic data')
    from cloud_training.nano_quality_gate import ValidationGuard
    try:ValidationGuard(contract['regression'])
    except (KeyError,ValueError,TypeError):problems.append('Invalid diagnostic regression guard')
    return problems


def validate_review_file(manifest_path, admission, contract):
    """Bind each manually reviewed row to the actual diagnostic inputs."""
    import hashlib,json
    from pathlib import Path
    parent=Path(manifest_path).resolve().parent
    review_path=parent/'data-review.json'
    digest=hashlib.sha256(review_path.read_bytes()).hexdigest()
    if digest!=admission.get('review_sha256') or digest!=contract.get('review_sha256'):
        raise ValueError('Changed or missing diagnostic review')
    manifest=json.loads(Path(manifest_path).read_text());review=json.loads(review_path.read_text())
    expected=[]
    for split,key in [('fit_train','train'),('development','validation')]:
        for line in (parent/manifest[key]['file']).read_text().splitlines():
            row=json.loads(line)
            expected.append((row['id'],split,hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True).encode()).hexdigest()))
    records=review.get('records',[])
    actual=[(r.get('id'),r.get('split'),r.get('row_sha256')) for r in records]
    if expected!=actual or not all(r.get('pass') is True for r in records):
        raise ValueError('Diagnostic review does not cover exact rows')
    suite=parent/'development-suite.json'
    if hashlib.sha256(suite.read_bytes()).hexdigest()!=contract.get('development_suite_sha256'):
        raise ValueError('Changed diagnostic development suite')
