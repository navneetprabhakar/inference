import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from goal_training_records import encode_training_row


def test_causal_replay_requires_opt_in_and_masks_only_real_targets():
    row = {'objective': 'causal_lm', 'tokens': [100, 101, 1, 102]}
    with pytest.raises(ValueError):
        encode_training_row(None, row)
    ids, mask, n = encode_training_row(None, row, True)
    assert n == 4 and ids[:n].tolist() == row['tokens']
    assert mask[:3].tolist() == [1, 1, 1]
    assert np.count_nonzero(mask[3:]) == 0 and len(ids) == 513


@pytest.mark.parametrize('tokens', [[100], [100] * 514, [100, 3], [100, -1], [100, 16384], [100, True]])
def test_replay_rejects_invalid_or_role_contaminated_sequences(tokens):
    with pytest.raises(ValueError):
        encode_training_row(None, {'objective': 'causal_lm', 'tokens': tokens}, True)
