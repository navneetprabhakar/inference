"""Fixed windows for the second controlled English pilot execution schema."""
import math
import os
import signal
import time
from datetime import datetime

LEASE = 270 * 60
CHECKPOINT = 600
QUALIFICATION = 60 * 60
ARM = 1350
BACKUP = 35 * 60
CONTINGENCY = 20 * 60
TAIL = BACKUP + CONTINGENCY
CAP = 30
MIN_RATE = 3.673385 + 200 * .000136986

def timestamp(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Explicit UTC offset required")
    return stamp.timestamp()

def qualification_window(config, now):
    start = timestamp(config["lease_start_utc"])
    stop = timestamp(config["provider_stop_utc"])
    if not start <= now < stop or not 0 < stop - start <= LEASE:
        raise ValueError("Invalid or expired lease")
    # Absolute boot + qualification budget prevents a delayed service from resetting its clock.
    deadline = min(start + 20 * 60 + QUALIFICATION, now + QUALIFICATION, stop - TAIL - 60)
    if deadline - now < CHECKPOINT:
        raise ValueError("Qualification window exhausted")
    return deadline, math.floor(deadline - now) + 30

def forecast(timings, decode):
    def observed(key):
        values = timings[key]
        if not isinstance(values,list) or not values or any(type(v) not in (float,int) or not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Missing or invalid measurements for "+key)
        return max(values)
    checkpoint = observed("checkpoint")
    if checkpoint > CHECKPOINT / 2:
        raise ValueError("Observed checkpoint exceeds half the reserved window")
    # 40 updates; step zero and eight 5-update observation boundaries may save.
    # Include an extra periodic save per arm and use the slowest observed cycle.
    before_final_save = observed("startup") + 40*observed("update") + 9*observed("evaluation") + 9*checkpoint
    # The trainer stops admitting updates at deadline minus CHECKPOINT.
    arm = math.ceil(1.5 * before_final_save + max(CHECKPOINT, 1.5 * checkpoint)) + 6
    if arm > ARM:
        raise ValueError(f"Projected arm {arm}s exceeds {ARM}s allocation")
    if type(decode) not in (int,float) or not math.isfinite(decode) or not 0 < decode <= 5400:
        raise ValueError("Decode exceeds allocation")
    return {"arm_seconds":arm,"decode_seconds":decode,"remaining_seconds":2*arm+decode}

def stop_group(child, grace=5):
    # The group leader can exit on TERM while a grandchild ignores it.
    try:
        os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:
        child.wait()
        return
    end = time.monotonic()+grace
    while time.monotonic()<end:
        child.poll()
        try:
            os.killpg(child.pid,0)
        except ProcessLookupError:
            break
        time.sleep(min(.05,grace))
    try:
        os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait()
