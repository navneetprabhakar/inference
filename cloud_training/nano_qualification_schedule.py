"""Validation schedules for controlled restart qualification; no compute launch."""

def restart_branches():
    # Terminal max_updates forces evaluation. Cadence1 makes the split boundary
    # an ordinary scheduled observation in BOTH runs; never weaken state compare.
    return {
        'uninterrupted': {'max_updates': 2, 'eval_every_updates': 1},
        'split_first': {'max_updates': 1, 'eval_every_updates': 1},
        'split_resume': {'max_updates': 1, 'eval_every_updates': 1},
    }


def validate_restart_branches(branches):
    if branches != restart_branches():
        raise ValueError('Qualification requires matching every-update validation and 2 versus 1+1 updates')
    return True
