import unittest
from cloud_training.conversation_overlap import rejection_reason,user_sequence,normalize


class OverlapTests(unittest.TestCase):
    def test_shared_greeting_does_not_erase_different_tasks(self):
        messages=[{'role':'user','content':'  HI  '},{'role':'assistant','content':'Hello'},
                  {'role':'user','content':'Help me arrange my notes.'}]
        self.assertIsNone(rejection_reason(messages,{'hi','explain gravity'},set()))

    def test_full_sequence_stays_excluded_even_if_all_greetings(self):
        messages=[{'role':'user','content':'Hello'}]
        self.assertEqual(rejection_reason(messages,{'hello'},{user_sequence(messages)}),'exact_user_sequence_overlap')

    def test_meaningful_prompt_and_unicode_equivalent_remain_excluded(self):
        messages=[{'role':'user','content':'Ｈｉ'},{'role':'user','content':' What are the four seasons? '}]
        self.assertEqual(normalize('Ｈｉ'),'hi')
        self.assertEqual(rejection_reason(messages,{'hi','what are the four seasons?'},set()),'substantive_user_prompt_overlap')


if __name__=='__main__':unittest.main()
