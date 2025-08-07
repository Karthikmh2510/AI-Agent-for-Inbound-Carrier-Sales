"""
A stateless relay: POST pushes one analytics record into RAM,
GET pops the newest record and immediately discards it.
Nothing is written to disk or a DB.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from typing import Optional, List

router = APIRouter(prefix="/analytics", tags=["analytics"])
DATA_STORE: List[dict] = []

# Step 1: Define Pydantic data model for validation
class CallAnalytics(BaseModel):
    carrier_name: Optional[str]
    mc_number: Optional[str]
    offer_amount: Optional[float] = None
    counter_offer_amount: Optional[float] = None
    final_rate: float
    negotiation_outcome: Optional[str]
    call_outcome: Optional[str]
    sentiment: Optional[str]
    timestamp: Optional[datetime] = None

    
    @field_validator('offer_amount', 'counter_offer_amount', 'final_rate', mode='before')
    def sanitize_currency(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            clean = v.replace("$", "").replace(",", "")
            return float(clean)
        return v
    
    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_timestamp(cls, v):
        return v or datetime.now(timezone.utc)
    
# Step 2: Create POST endpoint to receive data
@router.post("", response_model=CallAnalytics)
async def receive_call_data(data: CallAnalytics) -> CallAnalytics:
    # Example validation: if no outcome, reject
    if not data.call_outcome:
        raise HTTPException(status_code=400, detail="Missing call_outcome")

    # Step 3: Process or store the data (e.g., save to DB, log, queue)
    # For now, just log it
    DATA_STORE.append(data.model_dump())

    return data

@router.get("/events", response_model=List[CallAnalytics])
async def get_events():
    return DATA_STORE[-200:]  # return last 200 events