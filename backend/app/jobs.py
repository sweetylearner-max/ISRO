"""Async job store (AGENTS.md §8).

In-memory dict keyed by job_id, mirrored to disk so a Space restart doesn't lose
a finished dossier. Pipelines run in a threadpool so the event loop stays
responsive during the (CPU-bound, 10-30s) TLS search. Jobs auto-expire after
JOB_TTL_SECONDS. Progress callbacks map per-stage progress onto a global 0..1 bar.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from . import config

# Global progress budget per stage: (start, span). Sums to 1.0.
_STAGE_WEIGHTS: dict[str, tuple[float, float]] = {
    "queued": (0.00, 0.00),
    "fetching": (0.00, 0.15),
    "detrending": (0.15, 0.10),
    "searching": (0.25, 0.50),
    "folding": (0.75, 0.07),
    "vetting": (0.82, 0.10),
    "explaining": (0.92, 0.08),
    "complete": (1.00, 0.00),
}


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)

    # --- lifecycle ---------------------------------------------------------
    def create(self) -> str:
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "stage": "queued",
                "progress": 0.0,
                "error": None,
                "result": None,
                "_created": time.time(),
            }
        return job_id

    def _set(self, job_id: str, **fields) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(fields)

    def progress_fn(self, job_id: str) -> Callable[[str, float], None]:
        def on_progress(stage: str, pct: float) -> None:
            start, span = _STAGE_WEIGHTS.get(stage, (0.0, 0.0))
            glob = min(1.0, start + span * max(0.0, min(pct, 1.0)))
            self._set(job_id, stage=stage, progress=round(glob, 4), status="running")
        return on_progress

    def submit(self, job_id: str, fn: Callable[[Callable[[str, float], None]], dict]) -> None:
        """Run fn(on_progress) -> result dict in a worker thread."""
        def _run() -> None:
            self._set(job_id, status="running", stage="fetching", progress=0.01)
            try:
                result = fn(self.progress_fn(job_id))
                self._set(
                    job_id, status="done", stage="complete", progress=1.0, result=result, error=None
                )
                self._persist(job_id)
            except Exception as exc:  # noqa: BLE001 - map to friendly error, never leak traces
                msg = getattr(exc, "args", [None])
                friendly = str(exc) if msg and msg[0] else "The analysis failed unexpectedly."
                self._set(job_id, status="error", stage="complete", progress=1.0, error=friendly)

        self._executor.submit(_run)

    def get(self, job_id: str) -> Optional[dict]:
        self._expire()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return {k: v for k, v in job.items() if not k.startswith("_")}
        # Fall back to disk (survives restart).
        disk = self._load(job_id)
        return disk

    # --- disk mirror -------------------------------------------------------
    def _job_file(self, job_id: str):
        return config.CACHE_DIR / f"job_{job_id}.json"

    def _persist(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            payload = {k: v for k, v in job.items() if not k.startswith("_")}
        try:
            self._job_file(job_id).write_text(json.dumps(payload))
        except Exception:  # noqa: BLE001
            pass

    def _load(self, job_id: str) -> Optional[dict]:
        p = self._job_file(job_id)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:  # noqa: BLE001
                return None
        return None

    def _expire(self) -> None:
        now = time.time()
        with self._lock:
            dead = [j for j, v in self._jobs.items() if now - v.get("_created", now) > config.JOB_TTL_SECONDS]
            for j in dead:
                self._jobs.pop(j, None)


store = JobStore()
