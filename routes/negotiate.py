
from functools import lru_cache
import os
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
from routes.negotiate_graph import run_negotiation

load_dotenv()
router = APIRouter(prefix="/evaluate-offer", tags=["negotiation"])

# ───────────────────────── CSV lookup ─────────────────────────────────────────
@lru_cache
def rate_lookup() -> pd.Series:
    path = os.getenv("LOADS_CSV_PATH", "/app/data/loads.csv")
    
    if not os.path.exists(path):
        raise RuntimeError(f"CSV not found → {path}")
    df = pd.read_csv(path, dtype={"load_id": str})
    return df.set_index("load_id")["loadboard_rate"]  # Series: load_id → rate

# ───────────────────────── Pydantic models ────────────────────────────────────
class OfferIn(BaseModel):
    load_id: str
    offer: float 
    attempts: int 

    @field_validator("offer", mode="before")
    @classmethod
    def sanitize_offer(cls, v):
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").strip()
            return float(cleaned)
        return v
    
# ────────────────────────── Response model ───────────────────────────────────
class OfferOut(BaseModel):
    status: str            # "accept", "counter", or "reject"
    target_rate: float
    message: str
    attempts: int          # echo back so the agent can track rounds
    handoff: bool        # True => transfer to human rep now
    final: bool          # True => terminal (accept/reject or max attempts)

# ───────────────────────── route ------------------------------------------------
@router.post("", response_model=OfferOut)
def evaluate_offer(payload: OfferIn):
    rates = rate_lookup()
    if payload.load_id not in rates:
        raise HTTPException(404, "Load ID not found")

    board_rate = float(rates[payload.load_id])

    result = run_negotiation(
        board_rate=board_rate,
        initial_offer=payload.offer,
        attempts=payload.attempts
    )
    # ensure required keys present
    result.setdefault("handoff", result.get("status") == "accept")
    result.setdefault("final",   result.get("status") in ("accept", "reject"))
    result["attempts"] = payload.attempts
    return result
