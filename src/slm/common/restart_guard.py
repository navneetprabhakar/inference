"""Owner's 2026-10-21 restart boundary. Remove only after new explicit approval.

There is deliberately no environment variable or legacy launch receipt bypass.
This guard blocks the preserved runtime, not arbitrary external Python programs.
"""
def require_training_approval():
    raise RuntimeError(
        'English SLM restart is DESIGN ONLY: initialization, weight loading, '
        'training and resume are disabled pending fresh explicit owner approval.'
    )
