# src/routes/handoff.py
import os, uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from twilio.rest import Client
from fastapi.responses import Response

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER      = os.getenv("TWILIO_NUMBER")  # E.164, your Twilio caller ID
PUBLIC_BASE_URL    = os.getenv("PUBLIC_BASE_URL") # e.g., https://carrier-sales-api.fly.dev

if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_NUMBER and PUBLIC_BASE_URL):
    raise RuntimeError("Missing Twilio env vars")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
router = APIRouter(prefix="/handoff", tags=["handoff"])

class HandoffIn(BaseModel):
    carrier_number: str = Field(..., description="E.164, e.g. +13125551234")
    rep_number:     str = Field(..., description="E.164")
    case_id:        str | None = None

class HandoffOut(BaseModel):
    conference: str
    rep_call_sid: str
    carrier_call_sid: str

@router.post("", response_model=HandoffOut)
def start_handoff(payload: HandoffIn):
    """
    Create a Twilio conference and dial both the rep and the carrier into it.
    The bot ends the web call after calling this endpoint.
    """
    conf_name = payload.case_id or f"deal-{uuid.uuid4().hex[:8]}"

    # Build TwiML URLs that put each leg into the same conference
    rep_url     = f"{PUBLIC_BASE_URL}/twiml/voice?room={conf_name}&role=rep"
    carrier_url = f"{PUBLIC_BASE_URL}/twiml/voice?room={conf_name}&role=carrier"

    try:
        rep_call = client.calls.create(
            to=payload.rep_number,
            from_=TWILIO_NUMBER,
            url=rep_url,    # TwiML fetched by Twilio to control the call
        )
        carrier_call = client.calls.create(
            to=payload.carrier_number,
            from_=TWILIO_NUMBER,
            url=carrier_url,
        )
    except Exception as e:
        raise HTTPException(502, f"Twilio call creation failed: {e}")

    return {
        "conference": conf_name,
        "rep_call_sid": rep_call.sid,
        "carrier_call_sid": carrier_call.sid,
    }

# TwiML generator: put a leg into the named conference
from fastapi import APIRouter, Request
twiml_router = APIRouter(tags=["twiml"])

@twiml_router.get("/twiml/voice")
def voice_twiml(request: Request):
    room = request.query_params.get("room")
    role = request.query_params.get("role", "caller")
    if not room:
        return Response("<Response><Hangup/></Response>", media_type="application/xml")

    # rep joins and starts conference immediately; carrier joins unmuted
    start_on_enter = "true" if role == "rep" else "true"
    end_on_exit    = "true" if role == "rep" else "false"

    twiml = f"""
    <Response>
    <Dial>
        <Conference startConferenceOnEnter="{start_on_enter}"
                    endConferenceOnExit="{end_on_exit}">
        {room}
        </Conference>
    </Dial>
    </Response>
    """.strip()
    return Response(twiml, media_type="application/xml")
