# from functools import lru_cache
# import os

# import pandas as pd
# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel, Field
# from dotenv import load_dotenv
# load_dotenv()

# router = APIRouter(prefix="/evaluate-offer", tags=["negotiation"])


# # ---------- helpers -----------------------------------------------------------
# @lru_cache
# def rate_lookup() -> pd.Series:
#     csv_path = os.getenv("LOADS_CSV_PATH")
#     df = pd.read_csv(csv_path, dtype={"load_id": str})
#     return df.set_index("load_id")["loadboard_rate"]  # Series: load_id → rate


# # ---------- request / response models ----------------------------------------
# class OfferIn(BaseModel):
#     load_id: str = Field(..., example="L0001")
#     offer: float = Field(..., gt=0, example=2000)
#     attempts: int = Field(1, ge=1, le=3, description="Current back-and-forth count")


# class OfferOut(BaseModel):
#     status: str  # accept | counter | reject
#     target_rate: float
#     message: str


# # ---------- route -------------------------------------------------------------
# MAX_MARGIN = 0.15  # accept if offer within 15 % of board rate
# COUNTER_STEP = 0.05  # counter ↑ 5 % from driver’s last offer


# @router.post("", response_model=OfferOut)
# def evaluate_offer(payload: OfferIn):
#     rates = rate_lookup()
#     if payload.load_id not in rates:
#         raise HTTPException(404, "Load ID not found")

#     board_rate = float(rates[payload.load_id])
#     delta = board_rate - payload.offer
#     rel_diff = delta / board_rate  # positive when offer below board rate

#     # 1) Accept?
#     if rel_diff <= MAX_MARGIN:
#         return OfferOut(
#             status="accept",
#             target_rate=payload.offer,
#             message="Great – we can lock you in at that rate!",
#         )

#     # 2) Counter (up to 3 attempts)
#     if rel_diff <= 0.30 and payload.attempts < 3:
#         counter = payload.offer + board_rate * COUNTER_STEP
#         return OfferOut(
#             status="counter",
#             target_rate=round(counter, 2),
#             message=f"The best we can do is ${counter:.0f}. Does that work?",
#         )

#     # 3) Reject
#     return OfferOut(
#         status="reject",
#         target_rate=board_rate,
#         message="Sorry, we can’t move that far off the board rate.",
#     )

from functools import lru_cache
import os
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from .negotiate_graph import run_negotiation

load_dotenv()

router = APIRouter(prefix="/evaluate-offer", tags=["negotiation"])

# ───────────────────────── CSV lookup ─────────────────────────────────────────
@lru_cache
def rate_lookup() -> pd.Series:
    # path = os.getenv("LOADS_CSV_PATH", "./data/loads.csv")
    path = "./data/loads.csv"
    if not os.path.exists(path):
        raise RuntimeError(f"CSV not found → {path}")
    df = pd.read_csv(path, dtype={"load_id": str})
    return df.set_index("load_id")["loadboard_rate"]  # Series: load_id → rate

# ───────────────────────── Pydantic models ────────────────────────────────────
class OfferIn(BaseModel):
    load_id: str
    offer: float = Field(..., gt=0)
    attempts: int = Field(1, ge=1, le=3)

class OfferOut(BaseModel):
    status: str
    target_rate: float
    message: str

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
    return result
