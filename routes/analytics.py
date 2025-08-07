"""
src/routes/analytics.py
─────────────────────────────────────────────────────────────
Stateless relay for call-analytics data:

  • POST /analytics  – HappyRobot sends JSON after each call
  • GET  /analytics  – next system fetches the record exactly once

No database or file I/O — the latest record lives only in RAM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/analytics", tags=["analytics"])

# ──────────────────────
# 1) Payload schema
# ──────────────────────
class CallAnalytics(BaseModel):
    carrier_name:            Optional[str]
    mc_number:               Optional[str]
    offer_amount:            float
    counter_offer_amount:    float
    final_rate:              float
    negotiation_outcome:     Optional[str]
    call_outcome:            Optional[str]
    sentiment:               Optional[str]
    timestamp:               str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )

    # allow "$2,700" style strings and coerce to float
    @field_validator("offer_amount", "counter_offer_amount", "final_rate", mode="before")
    @classmethod
    def strip_currency(cls, v):
        if isinstance(v, str):
            return float(v.replace("$", "").replace(",", "").strip())
        return v


# ──────────────────────
# 2) In-memory buffer
# ──────────────────────
_buffer: Optional[dict] = None  # holds the most-recent record


# ──────────────────────
# 3) POST  /analytics
# ──────────────────────
@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def push(payload: CallAnalytics) -> Response:
    """
    Overwrite the buffer with the newest analytics record.
    Returns 204 No Content (no response body).
    """
    global _buffer
    if not payload.call_outcome:
        raise HTTPException(400, detail="Missing call_outcome")

    _buffer = payload.model_dump()  # store latest record
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ──────────────────────
# 4) GET   /analytics
# ──────────────────────
@router.get("", response_model=CallAnalytics | None)
def pull():
    """
    Pop & return the newest analytics record.
    If none is waiting, respond 204 No Content.
    """
    global _buffer
    if _buffer is None:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    record, _buffer = _buffer, None  # pop & clear
    return record
