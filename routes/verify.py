import os
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()

router = APIRouter(prefix="/verify-mc", tags=["carriers"])

FMCSA_URL = (
    "https://mobile.fmcsa.dot.gov/qc/services/carriers/docket-number/"
    "{mc}?webKey={key}"
)
WEBKEY = os.getenv("FMCSA_WEBKEY")  # set this in production


# ---------- response model ----------------------------------------------------
class VerifyResp(BaseModel):
    mc_number: str = Field(..., example="123456")
    eligible: bool
    status: str
    carrier_name: str | None = None


# ---------- route -------------------------------------------------------------
@router.get("", response_model=VerifyResp)
async def verify_mc(
    mc_number: str = Query(..., regex=r"^\d{3,7}$", description="Carrier MC #")
):
    """
    Look up the carrier in FMCSA.  If FMCSA_WEBKEY is not configured, return a
    mock success response so the PoC keeps working.
    """
    if not WEBKEY:
        # ----- demo fallback -----
        return {
            "mc_number": mc_number,
            "eligible": True,
            "status": "MOCK_SUCCESS",
            "carrier_name": "Demo Carrier Inc.",
        }

    url = FMCSA_URL.format(mc=mc_number, key=WEBKEY)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)

    if r.status_code != 200:
        raise HTTPException(r.status_code, "FMCSA lookup failed")

    data = r.json()
    eligible = bool(data)
    name = data[0]["legalName"] if eligible else None
    return {
        "mc_number": mc_number,
        "eligible": eligible,
        "status": "SUCCESS" if eligible else "NOT_FOUND",
        "carrier_name": name,
    }
