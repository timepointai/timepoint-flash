"""TDF (Timepoint Data Format) export endpoint.

Exports timepoints as TDF records — the JSON interchange format used across
the Timepoint suite (Flash, Pro, Clockchain, SNAG-Bench, Proteus).

A TDF record contains:
  - id: Flash UUID (or Clockchain canonical URL in other services)
  - version: TDF schema version (currently "1.0.0")
  - source: originating service ("flash")
  - timestamp: ISO-8601 creation time
  - provenance: generator metadata
  - payload: temporal-spatial-narrative content
  - tdf_hash: SHA-256 of the canonicalised payload (content-addressed)

The output conforms to the TDFRecord schema defined in the ``timepoint-tdf``
library (https://github.com/timepoint-ai/timepoint-tdf).

See also: docs/AGENTS.md § TDF for the full format specification.
"""

import logging
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import Timepoint

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tdf"])


@router.get("/timepoints/{timepoint_id}/tdf")
async def get_timepoint_tdf(
    timepoint_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Export a single timepoint as a TDF record.

    The response is a JSON object conforming to the TDFRecord schema
    from the ``timepoint-tdf`` library.  The ``tdf_hash`` field is a
    SHA-256 digest of the canonicalised ``payload`` dict, making each
    record content-addressable.
    """
    result = await db.execute(select(Timepoint).where(Timepoint.id == timepoint_id))
    tp = result.scalar_one_or_none()
    if tp is None:
        raise HTTPException(status_code=404, detail="Timepoint not found")

    ts = tp.created_at
    if ts and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    record = {
        "id": tp.id,
        "version": tp.tdf_version,
        "source": "flash",
        "timestamp": ts.isoformat() if ts else None,
        "provenance": {
            "generator": "timepoint-flash",
            "run_id": None,
            "confidence": None,
            "flash_id": tp.id,
        },
        "payload": tp.tdf_payload,
        "tdf_hash": tp.tdf_hash,
    }

    return JSONResponse(content=record)
