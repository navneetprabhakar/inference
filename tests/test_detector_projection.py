"""Literal detector EOS must not split one source window into two predictions."""
# Creator: Navneet Prabhakar
from slm.data.detector_projection import fasttext_line


def test_eos_is_escaped_in_view_without_mutating_original():
    raw='Some original text </s> with a second sentence.\nNext line.'
    view=fasttext_line(raw)
    assert '</s>' in raw and '</s>' not in view and '\n' not in view
    assert view=='Some original text < /s > with a second sentence. Next line.'


def test_normal_windows_and_multiple_eos_are_deterministic():
    assert fasttext_line('Ordinary prose.')=='Ordinary prose.'
    assert fasttext_line('</s> </s>').count('< /s >')==2
