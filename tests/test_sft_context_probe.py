"""Synthetic context workloads do not imply training or semantic quality."""
# Creator: Navneet Prabhakar
import numpy as np
import pytest
from slm.eval.sft_context_probe import workload, run
from slm.common.tokenizer import OFFSET


def test_nested_shifted_content_only_workloads_and_half_masks():
    a, b = workload(8, 300, 16), workload(16, 300, 16)
    np.testing.assert_array_equal(a[0], b[0][:, :8])
    np.testing.assert_array_equal(a[1], b[1][:, :8])
    np.testing.assert_array_equal(b[0][:, 1:], b[1][:, :-1])
    assert b[0].min() >= OFFSET and b[0].max() < 300
    assert a[2].sum() == 4 and b[2].sum() == 8
    assert not a[2][0, :4].any() and a[2][0, 4:].all()


@pytest.mark.parametrize('length,vocab,maximum', [(0, 300, 16), (17, 300, 16), (True, 300, 16), (8, OFFSET, 16)])
def test_invalid_workloads_refused(length, vocab, maximum):
    with pytest.raises(ValueError): workload(length, vocab, maximum)


def test_output_or_workload_refused_before_model_allocation(tmp_path):
    path = tmp_path/'existing'; path.write_text('keep')
    with pytest.raises(FileExistsError): run(tmp_path/'missing', 'x', path, 1024)
    assert path.read_text() == 'keep'
    with pytest.raises(ValueError, match='1024/2048'): run(tmp_path/'missing', 'x', tmp_path/'no-output', 3)
    assert not (tmp_path/'no-output').exists()
