import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from inference_guard import stop_requested, violation


class InferenceGuardTest(unittest.TestCase):
    def test_thermal_memory_swap_and_disk_stops(self):
        baseline = {"swap_used_mb": 100}
        healthy = {"thermal_state": 0, "free_disk_bytes": 20 * 2**30, "mlx_peak_bytes": 1, "mlx_allocator_bytes": 1, "swap_used_mb": 100}
        self.assertIsNone(violation(healthy, baseline))
        self.assertEqual(violation({**healthy, "thermal_state": 3}, baseline), "critical_thermal")
        self.assertEqual(violation({**healthy, "mlx_allocator_bytes": 13 * 2**30}, baseline), "mlx_memory")
        self.assertEqual(violation({**healthy, "swap_used_mb": 1125}, baseline), "swap_growth")
        self.assertEqual(violation({**healthy, "free_disk_bytes": 14 * 2**30}, baseline), "disk_reserve")

    def test_stop_requested_ignores_training_stop(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            training_stop = root / "runs/sft-v3/STOP"
            training_stop.parent.mkdir(parents=True)
            training_stop.write_text("Bounded experiment complete. Review required before further training.\n")

            self.assertFalse(stop_requested(root))

    def test_stop_requested_honors_inference_stop(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inference_stop = root / "runs/codex-corpus-review-v2/STOP"
            inference_stop.parent.mkdir(parents=True)
            inference_stop.write_text("Stop inference.\n")

            self.assertTrue(stop_requested(root))


if __name__ == "__main__":
    unittest.main()
