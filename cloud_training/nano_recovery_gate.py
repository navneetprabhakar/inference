"""Offline, fail-closed decision gate for a NEW Ganesh recovery campaign.

No cloud calls, provisioning, training or authority is created by this module.
Receipts must be produced by real checks; trusted local receipts are not signatures.
Old launchers do not invoke this gate and must not be used for the new campaign.
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import math

QUALIFICATION = ('cuda_runtime', 'exact_restart', 'signal_recovery',
                 'gcs_restore', 'upload_rejection', 'provider_stop')
STAGES = ('qualification', 'fit', 'curriculum', 'release')

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('UTC timestamp string required')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone required')
    return parsed.astimezone(dt.timezone.utc)

def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0

def inspect(root, request, stage, *, now=None):
    """Return all blockers. Unknown/missing evidence never passes by omission."""
    root = Path(root).resolve()
    now = now or dt.datetime.now(dt.timezone.utc)
    errors = []
    def need(condition, reason):
        if not condition:
            errors.append(reason)
    need(stage in STAGES, 'Unknown stage')
    need(request.get('schema') == 1, 'Unsupported request schema')
    need(request.get('scope') == 'ganesh_english_recovery', 'Wrong campaign scope')
    need(request.get('path') in ('exact_resume', 'no_resume_diagnostic'), 'Unknown qualification path')
    need(request.get('machine') in ('g2-standard-8', 'a2-highgpu-1g'),
         'Only a single L4 or A100 40GB machine is supported; approval must bind the exact choice')
    need(type(request.get('resource_count')) is int and request['resource_count'] == 1, 'Exactly one campaign VM required')
    need(request.get('provider_action') == 'STOP' and request.get('disk_auto_delete') is False,
         'STOP and non-auto-delete recovery disk required')
    need(request.get('automatic_retry') is False, 'Automatic retries forbidden')
    need(request.get('automatic_restart') is False, 'Automatic restart forbidden')
    need(request.get('http_enabled') is False, 'HTTP must remain off')
    bindings = request.get('files', {})
    need(isinstance(bindings, dict) and bool(bindings), 'Input bindings missing')
    if isinstance(bindings, dict):
        for name, expected in bindings.items():
            p = root / name
            valid = (isinstance(name, str) and not Path(name).is_absolute()
                     and '..' not in Path(name).parts and p.resolve().is_relative_to(root)
                     and not p.is_symlink() and p.is_file())
            if not valid:
                errors.append('Invalid bound path: ' + str(name)); continue
            need(isinstance(expected, str) and digest(p) == expected, 'Changed input: ' + name)
    need(request.get('local_checks_passed') is True, 'Local checks not passed')
    need(request.get('launcher_integrated') is True, 'New launcher integration not verified')
    # Authorization is a separate receipt tied to this exact immutable specification.
    spec = {k: v for k, v in request.items() if k not in ('authorization', 'evidence')}
    spec_hash = hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    auth = request.get('authorization') or {}
    need(auth.get('spec_sha256') == spec_hash, 'Approval does not bind this specification')
    need(auth.get('explicit_user_approval') is True and bool(auth.get('approval_reference')),
         'Fresh explicit user approval missing')
    if request.get('path') == 'no_resume_diagnostic':
        need(auth.get('no_resume_exception') is True, 'No-resume exception not explicitly approved')
        need(stage in ('qualification', 'fit'), 'Diagnostic cannot enter production or release')
        need(request.get('resume_from') is None, 'No-resume path cannot resume')
    cap, reserve = auth.get('cap_usd'), request.get('reserve_usd')
    cost = request.get('maximum_incremental_cost_usd')
    need(positive(cap) and positive(reserve) and positive(cost), 'Finite positive cap/cost/reserve required')
    if all(positive(x) for x in (cap, reserve, cost)):
        need(cost <= cap and reserve < cost, 'Envelope exceeds approved cap or has no compute allowance')
    try:
        start, stop = timestamp(request['lease_start_utc']), timestamp(request['provider_stop_utc'])
        backup = request['backup_reserve_seconds']
        need(type(backup) is int and backup >= 900, 'Backup reserve must be at least 900 seconds')
        need(start <= now < stop, 'Lease inactive or expired')
        need(stop > start, 'Invalid lease ordering')
        if type(backup) is int:
            need((stop-now).total_seconds() > backup, 'No time remaining outside backup reserve')
        if request.get('training_inputs'):
            worker_stop=timestamp(request['worker_stop_utc'])
            need(now < worker_stop < stop and (stop-worker_stop).total_seconds()>=900, 'Worker STOP must preserve provider backup reserve')
        deadline = timestamp(auth['expires_utc'])
        need(now < deadline and stop <= deadline, 'Approval expired or shorter than lease')
    except (KeyError, TypeError, ValueError):
        errors.append('Valid fixed UTC lease and approval expiry required')
    # A boolean is insufficient evidence: verify scope, binding, raw receipt payload.
    def proof(name):
        entry = (request.get('evidence') or {}).get(name, {})
        path = entry.get('path', '')
        p = root / path
        valid = (bool(path) and not Path(path).is_absolute() and '..' not in Path(path).parts
                 and p.resolve().is_relative_to(root) and p.is_file() and not p.is_symlink())
        if not valid or digest(p) != entry.get('sha256'):
            errors.append('Missing/changed receipt: ' + name); return None
        try:
            body = json.loads(p.read_text())
        except (ValueError, OSError):
            errors.append('Invalid receipt: ' + name); return None
        need(body.get('status') == 'pass' and body.get('check') == name
             and body.get('spec_sha256') == spec_hash, 'Failed/foreign receipt: ' + name)
        return body
    for name in ('fresh_inventory', 'input_backups', 'price_quote'):
        body = proof(name)
        if body:
            try:
                age = (now-timestamp(body['checked_utc'])).total_seconds()
                need(0 <= age <= (900 if name=='fresh_inventory' else 86400), 'Stale receipt: ' + name)
            except (KeyError, TypeError, ValueError):
                errors.append('Missing receipt time: ' + name)
    if request.get('training_inputs'):
        # Real execution requests must carry a rate-derived envelope, not a guessed total.
        entry=(request.get('evidence') or {}).get('price_quote',{})
        if entry.get('path'):
            try:
                quote=json.loads((root/entry['path']).read_text())
                rate=quote['hourly_rate_usd'];margin=quote['margin_multiplier']
                need(positive(rate) and positive(margin) and margin>=1.25, 'Priced compute margin missing')
                hours=(timestamp(request['provider_stop_utc'])-timestamp(request['lease_start_utc'])).total_seconds()/3600
                if positive(rate) and positive(margin) and positive(reserve) and positive(cost):
                    need(cost>=hours*rate*margin+reserve, 'Lease cost under-reserved')
            except (KeyError,ValueError,TypeError,OSError):errors.append('Complete rate-derived price quote required')
    if stage in ('fit', 'curriculum', 'release'):
        required = QUALIFICATION
        # Keeping an allocated GPU until work finishes avoids losing scarce
        # capacity. Only explicit user authority permits observing STOP at
        # closeout; its fixed configuration is still required before training.
        if request.get('provider_stop_validation') == 'closeout':
            need(auth.get('retain_vm_until_work_complete') is True,
                 'Deferring the STOP drill requires explicit retain-VM authority')
            if stage != 'release':
                required = tuple('provider_stop_configured' if n == 'provider_stop' else n
                                 for n in required)
        else:
            need(request.get('provider_stop_validation') in (None, 'before_fit'),
                 'Unknown provider STOP validation order')
        if request.get('path') == 'no_resume_diagnostic':
            required = tuple(n for n in QUALIFICATION if n not in ('exact_restart', 'signal_recovery'))
        for name in required:
            proof(name)
    if stage == 'fit':
        recipe = request.get('fit_recipe', {})
        need(recipe == {'max_updates': 64, 'max_epochs': 64, 'lr_multiplier': .25,
                        'packing_buffer': 1, 'context_tokens': 2048}, 'Frozen fit recipe mismatch')
    if stage in ('curriculum', 'release'):
        for name in ('fit_semantic_review', 'production_admission', 'production_preflight'):
            proof(name)
        need(request.get('production_parent') == 'immutable_base10b', 'Production parent must be fixed base10B')
        need(type(request.get('failed_learning_pilots')) is int and 0 <= request['failed_learning_pilots'] < 2, 'Two failed learning pilots or invalid failure count require HOLD')
    if stage == 'release':
        for name in ('development_selection', 'independent_review_ready'):
            proof(name)
        need(request.get('release_exposed') is False, 'Release suite already exposed or unspecified')
        need(isinstance(request.get('selected_candidate_sha256'), str)
             and len(request['selected_candidate_sha256']) == 64
             and all(c in '0123456789abcdef' for c in request['selected_candidate_sha256']), 'Select one candidate before release')
    return {'stage': stage, 'spec_sha256': spec_hash, 'allowed': not errors,
            'blockers': errors, 'scope': 'Offline evidence check only; not a cloud authorization mechanism'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--root', default='.')
    parser.add_argument('--stage', choices=STAGES, required=True)
    args = parser.parse_args()
    result = inspect(args.root, json.loads(Path(args.request).read_text()), args.stage)
    print(json.dumps(result, indent=2))
    return 0 if result['allowed'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
