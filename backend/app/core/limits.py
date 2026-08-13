"""Per-instance concurrency guard for the CPU-bound simulation endpoints.

An ``/api/optimize`` request runs a Monte-Carlo sweep over a policy grid of up
to 240 candidates. That work is single-threaded numpy -- integer elementwise
ops and RNG draws, no BLAS -- so it pins exactly one core for its whole
duration. Extra vCPUs make a single sweep no faster; they only let more sweeps
run side by side.

Container concurrency is deliberately set above the core count so cheap
requests (static assets, ``/api/scenarios``, ``/api/health``) stay responsive
while a sweep is in flight. Without a second bound, though, that same headroom
lets several sweeps land on one instance and thrash each other: N sweeps
sharing fewer than N cores each take roughly N times longer, and the instance
stops answering anything in time -- including the plain page load, which then
surfaces as a raw platform error rather than an app screen.

So the heavy endpoints take a slot from a bounded semaphore sized to the
container's CPU allocation, and callers that find none free get a clean JSON
429 immediately instead of queueing behind a sweep. The service holds no
per-request state, so Cloud Run is free to scale out and hand concurrent
visitors their own instances; this guard only stops one instance from
thrashing itself.

Sizing note: the endpoints are sync ``def`` handlers, so FastAPI runs them in
the AnyIO worker threadpool. A ``threading`` primitive is the right kind of
lock here.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from app.core.config import settings

BUSY_DETAIL = (
    "The simulator is busy running someone else's scenario right now. "
    "Please try again in a moment."
)

_slots = threading.BoundedSemaphore(settings.max_concurrent_simulations)


@contextmanager
def simulation_slot() -> Iterator[None]:
    """Hold a simulation slot for the duration of the block, or raise 429.

    Non-blocking on purpose: a caller that waits its turn would sit past the
    request timeout with no feedback, so failing fast with a retryable status
    is the friendlier outcome.
    """

    if not _slots.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail=BUSY_DETAIL,
            headers={"Retry-After": "5"},
        )
    try:
        yield
    finally:
        _slots.release()
