"""POST /analyze -> job; GET /jobs/{id} -> status/dossier."""
from __future__ import annotations

import base64
import re

from fastapi import APIRouter, HTTPException

from .. import config
from ..exoseer_core import catalog, ingest, run_pipeline
from ..exoseer_core.types import IngestError
from ..jobs import store
from ..schemas import AnalyzeRequest, JobCreated

router = APIRouter(tags=["analyze"])


def _decode_csv(csv_base64: str) -> bytes:
    # Tolerate a data-URL prefix.
    payload = re.sub(r"^data:[^,]*,", "", csv_base64.strip())
    try:
        return base64.b64decode(payload)
    except Exception as exc:  # noqa: BLE001
        raise IngestError("The uploaded file could not be decoded.") from exc


@router.post("/analyze", response_model=JobCreated, status_code=202)
def analyze(req: AnalyzeRequest) -> JobCreated:
    job_id = store.create()
    options = req.options.model_dump()

    def run(on_progress) -> dict:
        on_progress("fetching", 0.0)
        if req.source == "upload":
            if not req.csv_base64:
                raise IngestError("No CSV provided for upload.")
            lc = ingest.from_csv(_decode_csv(req.csv_base64), on_progress=on_progress)
            target, mission = "Uploaded CSV", "user"
        else:
            if not req.target:
                raise IngestError("Please enter a star name or ID.")
            if req.source == "catalog":
                target = catalog.resolve_target(req.target)
                entry = catalog.get_entry(req.target)
                mission = (entry or {}).get("mission") or req.mission
            else:
                target, mission = req.target, req.mission
            lc = ingest.from_mast(target, mission, req.sector_or_quarter, on_progress=on_progress)

        return run_pipeline(lc, target, mission, options, on_progress=on_progress)

    store.submit(job_id, run)
    return JobCreated(job_id=job_id)


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return job
