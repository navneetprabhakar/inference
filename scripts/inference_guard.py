"""Resource stop policy shared by host-only inference preparation."""
from pathlib import Path

DISK_MIN_BYTES = 15 * 2**30
MLX_MAX_BYTES = 12 * 2**30
SWAP_GROWTH_MAX_MB = 1024


def violation(health, baseline):
    """Return a stable stop reason, or None. Critical thermal never waits."""
    if health.get("thermal_state", 0) >= 3:
        return "critical_thermal"
    if health.get("free_disk_bytes", 0) < DISK_MIN_BYTES:
        return "disk_reserve"
    if health.get("mlx_peak_bytes", 0) > MLX_MAX_BYTES or health.get("mlx_allocator_bytes", 0) > MLX_MAX_BYTES:
        return "mlx_memory"
    if health.get("swap_used_mb") is not None and baseline.get("swap_used_mb") is not None and health["swap_used_mb"] - baseline["swap_used_mb"] > SWAP_GROWTH_MAX_MB:
        return "swap_growth"
    return None


def stop_requested(root):
    root = Path(root)
    return (root / "runs/codex-corpus-review-v2/STOP").exists()
