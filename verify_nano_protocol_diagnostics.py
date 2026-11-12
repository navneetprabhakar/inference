"""Protect diagnostic coverage against text-only selection and duplicate samples."""
import unittest

from cloud_training.nano_protocol_diagnostics import length_spread, source_group


class DiagnosticSamplingTests(unittest.TestCase):
    def test_call_frames_are_separate_from_text_only_tool_lessons(self):
        text = {'diagnostic_source':'tools', 'messages':[{'role':'assistant','content':'answer'}]}
        call = {'diagnostic_source':'tools', 'messages':[{'role':'assistant','tool_call':{'name':'calculate'}}]}
        self.assertNotEqual(source_group(text), source_group(call))
        self.assertEqual(source_group(call), 'tools/calculate')

    def test_mixed_tools_have_order_independent_group(self):
        messages = [{'tool_call':{'name':name}} for name in ('convert','calculate','convert')]
        row = {'diagnostic_source':'tools','messages':messages}
        self.assertEqual(source_group(row), 'tools/calculate,convert')

    def test_short_groups_never_repeat_a_conversation(self):
        rows = [{'id':i,'sequence_tokens':i+2} for i in range(2)]
        self.assertEqual([row['id'] for row in length_spread(rows,4)], [0,1])
        self.assertEqual(length_spread([],4), [])

    def test_selection_includes_longer_examples(self):
        rows = [{'id':i,'sequence_tokens':i+2} for i in range(10)]
        self.assertEqual([row['id'] for row in length_spread(rows,4)], [0,3,6,9])


if __name__ == '__main__':
    unittest.main()
