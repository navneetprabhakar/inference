"""Conservative dialogue decontamination without treating greetings as tasks."""
import unicodedata


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


# Explicitly narrow: factual questions and generic task followups are NOT exempt.
COURTESIES=frozenset(('hi','hi there','hey!','hello'))


def user_sequence(messages):
    return tuple(normalize(m['content']) for m in messages if m['role']=='user')


def rejection_reason(messages,development_prompts,development_sequences):
    sequence=user_sequence(messages)
    if sequence in development_sequences:return 'exact_user_sequence_overlap'
    if (set(sequence)-COURTESIES)&development_prompts:return 'substantive_user_prompt_overlap'
    return None
