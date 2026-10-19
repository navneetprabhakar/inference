"""Escape detector control syntax in a classifier-only line projection."""
# Creator: Navneet Prabhakar


def fasttext_line(text):
    if not isinstance(text,str):raise ValueError('Original text required')
    # fastText Dictionary::getLine treats a literal </s> word as an end of line.
    # Preserve original source text/offsets; escape only the detector input view.
    return text.replace('\n',' ').replace('\r',' ').replace('</s>','< /s >')
