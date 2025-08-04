from functools import lru_cache
from typing import List

import os
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()


router = APIRouter(prefix="/search-loads", tags=["loads"])


# ---------- helpers -----------------------------------------------------------
@lru_cache
def load_df() -> pd.DataFrame:
    """
    Read the CSV once per process. The two date columns are parsed as timestamps
    so we can filter / sort later if needed.
    """
    csv_path = os.getenv("LOADS_CSV_PATH", "/app/data/loads.csv")
   
    if not os.path.exists(csv_path):
        raise RuntimeError(f"CSV file not found → {csv_path}")
    
    return pd.read_csv(
        csv_path,
        parse_dates=["pickup_datetime", "delivery_datetime"],
        dtype={"load_id": str},
        na_filter=False,  # treat empty strings as NaN
    )


# ---------- response models ---------------------------------------------------
class LoadOut(BaseModel):
    load_id: str
    origin: str
    destination: str
    pickup_datetime: datetime
    delivery_datetime: datetime
    equipment_type: str
    loadboard_rate: int
    notes: str | None = None
    weight: int
    commodity_type: str
    num_of_pieces: int
    miles: int
    dimensions: str


class LoadResponse(BaseModel):
    loads: List[LoadOut]


# ---------- route -------------------------------------------------------------
@router.get("", response_model=LoadResponse)
def search_loads(
    origin: str = Query(..., min_length=2, description="Origin city or state"),
    destination: str = Query(..., min_length=2, description="Destination"),
    equipment_type: str = Query(..., min_length=2, description="e.g., Van, Reefer"),
    limit: int = Query(3, ge=1, le=10, description="Max rows to return"),
):
    """
    Return up to *limit* loads that match simple substring rules
    (case-insensitive).  You can replace this with full-text or SQL later.
    """
    df = load_df()
    mask = (
        df.origin.str.contains(origin, case=False, na=False)
        & df.destination.str.contains(destination, case=False, na=False)
        & df.equipment_type.str.contains(equipment_type, case=False, na=False)
    )
    matches = df[mask].head(limit)

    if matches.empty:
        raise HTTPException(404, detail="No matching loads")
    
    # Convert pandas.Timestamp → built-in datetime for Pydantic v2 validation.
    for col in ("pickup_datetime", "delivery_datetime"):
        matches[col] = (matches[col].dt.tz_localize(None).dt.to_pydatetime())

    return {"loads": matches.to_dict(orient="records")}


def get_board_rate(load_id: str) -> int | None:
    """
    Utility for other modules (e.g., negotiation) to fetch the loadboard_rate
    for a given load_id. Returns None if not found.
    """
    df = load_df()
    row = df.loc[df.load_id == load_id, "loadboard_rate"]
    if row.empty:
        return None
    return int(row.iloc[0])