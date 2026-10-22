"""Explicit system-wide monotonic clock for macOS Python3.9 process binding."""
import math
import time

def shared_clock():
    value=time.clock_gettime(time.CLOCK_MONOTONIC)
    if not math.isfinite(value) or value<0:raise ValueError('invalid_shared_monotonic_clock')
    return value
