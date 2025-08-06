from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Step 1: Define Pydantic data model for validation
class CallAnalytics(BaseModel):
    carrier_name: Optional[str]
    mc_number: Optional[str]
    offer_amount: float
    counter_offer_amount: float
    final_rate: float
    negotiation_outcome: Optional[str]
    call_outcome: Optional[str]
    sentiment: Optional[str]

    @field_validator('offer_amount', 'counter_offer_amount', 'final_rate', mode='before')
    def sanitize_currency(cls, v):
        if isinstance(v, str):
            # Remove $ and commas before conversion
            clean = v.replace('$', '').replace(',', '')
            return float(clean)
        return v
    
# Step 2: Create POST endpoint to receive data
@router.post("", response_model=CallAnalytics)
async def receive_call_data(data: CallAnalytics) -> CallAnalytics:
    # Example validation: if no outcome, reject
    if not data.call_outcome:
        raise HTTPException(status_code=400, detail="Missing call_outcome")

    # Step 3: Process or store the data (e.g., save to DB, log, queue)
    # For now, just log it
    json_str = data.model_dump_json()
    print("Received call analytics:", json_str)

    # Response back to confirm
    return {
        "carrier_name": data.carrier_name,
        "mc_number": data.mc_number,
        "offer_amount": data.offer_amount,
        "counter_offer_amount": data.counter_offer_amount,
        "final_rate": data.final_rate,
        "negotiation_outcome": data.negotiation_outcome,
        "call_outcome": data.call_outcome,
        "sentiment": data.sentiment
    }


