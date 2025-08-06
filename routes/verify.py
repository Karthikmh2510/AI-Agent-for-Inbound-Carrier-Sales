import os, re
import requests
from fastapi import APIRouter
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/verify-mc", tags=["carriers"])

# ────────────────────────────── ENV SETUP ────────────────────────────────────
WEBKEY = os.getenv("FMCSA_WEBKEY")  # set this in production


# ---------- response model ----------------------------------------------------
class VerifyResp(BaseModel):
    mc_number: str = Field(...)
    eligible: bool
    status: str
    carrier_name: str | None = None


# ---------- route -------------------------------------------------------------
@router.get("", response_model=VerifyResp)
def verify_mc(mc_number: str | int,
              webkey: str,
              timeout: int = 10) -> dict:
    """
    Look up an MC docket number via FMCSA QCMobile and return a
    compact status block.

    Returns
    -------
    dict with keys:
        mc_number     str   – digits only
        eligible      bool  – True if carrier record found
        status        str   – 'SUCCESS', 'NOT_FOUND', or API error message
        carrier_name  str|None
    """
    # 1. sanitise MC -> digits only
    mc_number = re.sub(r"\D", "", str(mc_number))
    url = f"https://mobile.fmcsa.dot.gov/qc/services/carriers/docket-number/{mc_number}"

    try:
        resp  = requests.get(url,
                             params={"webKey": webkey},
                             timeout=timeout)
        data  = resp.json()          # may be list, dict, or []
    except Exception as exc:         # network or JSON error
        return {
            "mc_number": mc_number,
            "eligible":  False,
            "status":    f"REQUEST_ERROR: {exc}",
            "carrier_name": None,
        }

    # 2. locate the carrier block regardless of wrapper
    carrier = None
    if isinstance(data, list) and data:
        carrier = data[0]
    elif isinstance(data, dict):
        if "content" in data and data["content"]:
            carrier = data["content"][0].get("carrier") \
                      or data["content"][0]
        elif "carrier" in data:
            carrier = data["carrier"]

    # 3. build return payload
    if carrier:
        name = (carrier.get("legalName")
                or carrier.get("dbaName")
                or carrier.get("entityName"))
        return {
            "mc_number": mc_number,
            "eligible":  True,
            "status":    "SUCCESS",
            "carrier_name": name,
        }

    # fall-back: empty list or explicit error dict
    status_msg = ("NOT_FOUND"
                  if not isinstance(data, dict)
                  else data.get("errorMessage", "NOT_FOUND"))
    return {
        "mc_number": mc_number,
        "eligible":  False,
        "status":    status_msg,
        "carrier_name": None,
    }