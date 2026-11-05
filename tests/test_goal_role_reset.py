import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_goal_role_reset import reset_roles, ROLE_IDS


def test_only_four_role_rows_change_and_are_distinct():
    x = np.random.default_rng(42).normal(size=(512, 64)).astype(np.float32)
    before = x.copy()
    y, norm = reset_roles(x, 73)
    assert np.array_equal(x, before)
    assert np.flatnonzero(np.any(x != y, axis=1)).tolist() == ROLE_IDS
    assert np.allclose(y[ROLE_IDS] @ y[ROLE_IDS].T, np.eye(4) * norm**2, atol=1e-5)
    assert np.array_equal(reset_roles(x, 73)[0], y)
    assert not np.array_equal(reset_roles(x, 74)[0], y)
