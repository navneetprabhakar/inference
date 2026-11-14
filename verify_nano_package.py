import unittest
from cloud_training.nano_package import MODULES,verify_module_closure
class PackageTests(unittest.TestCase):
    def test_actual_project_dependency_closure(self):
        self.assertEqual(verify_module_closure('.')['missing'],[])
    def test_omitted_context_or_guard_fails_locally(self):
        for missing in ('nano_context','nano_quality_gate','nano_corpus_guard'):
            with self.assertRaisesRegex(ValueError,missing):
                verify_module_closure('.',tuple(m for m in MODULES if m!=missing))
if __name__=='__main__':unittest.main()
