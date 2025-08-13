"""
routes/negotiate_graph.py
Negotiation rules:
- Accept if |offer - board| <= ACCEPT_WITHIN * board  → handoff to human
- Counter if within NEGOTIATE_WITHIN * board         → up to MAX_ATTEMPTS
- Reject otherwise or if attempts hit MAX_ATTEMPTS
"""

from __future__ import annotations
import json, os
from typing import TypedDict
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

# Optional LLM (kept, but fallback is deterministic)
try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
except Exception:
    ChatPromptTemplate = None
    ChatOpenAI = None

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
USE_LLM = bool(OPENAI_KEY and ChatOpenAI is not None)

# ---------- Tunables (env) ----------
ACCEPT_WITHIN     = float("0.10")  # ±10%
NEGOTIATE_WITHIN  = float("0.30")# up to ±30%
MAX_ATTEMPTS      = 3
# step concessions (as fraction of board) per attempt
COUNTER_STEPS     = [0.05, 0.08, 0.10]

if USE_LLM:
    LLM = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_KEY, temperature=0.2)
    SYSTEM = (
        "You are an expert freight broker.\n"
        "Return JSON with keys: status ('accept'|'counter'|'reject'), "
        "target_rate (number), message (string). Values are whole US dollars."
    )

class NegotiationState(TypedDict, total=False):
    board_rate: float
    offer: float
    last_driver_offer: float   # new field to remember it
    attempts: int
    result: dict   # {"status": str, "target_rate": float, "message": str, "handoff": bool, "final": bool}

def llm_round(board: float, offer: float) -> dict | None:
    if not USE_LLM:
        return None
    prompt = f"""{SYSTEM}

    Board rate: {board:.2f}
    Driver offer: {offer:.2f}

    Rules:
    - Accept if |offer - board| <= {ACCEPT_WITHIN:.2f} * board
    - Counter (toward board) if within {NEGOTIATE_WITHIN:.2f} * board
    - Reject if beyond that band or attempt cap is reached
    """
    resp = LLM.invoke(prompt)
    text = getattr(resp, "content", str(resp))
    try:
        return json.loads(text)
    except Exception:
        return None

def deterministic_round(board: float, offer: float, attempts: int) -> dict:
    gap = offer - board
    abs_pct = abs(gap) / board if board > 0 else 1.0

    # Accept in tight band
    if abs_pct <= ACCEPT_WITHIN:
        return {
            "status": "accept",
            "target_rate": float(round(offer)),
            "message": f"Sounds good. Confirming at ${round(offer):,}. Transferring you to a human rep.",
            "handoff": True,
            "final": True,
        }

    # Concession schedule & high-side caps (as % over board), tapered by attempt
    step = COUNTER_STEPS[min(max(attempts, 1) - 1, len(COUNTER_STEPS) - 1)]
    HIGH_CAPS = [0.25, 0.18, 0.12]  # attempt 1/2/3 → +25%, +18%, +12% over board
    high_cap = HIGH_CAPS[min(max(attempts, 1) - 1, len(HIGH_CAPS) - 1)]
    high_ceiling = board * (1 + high_cap)

    if gap >= 0:
        # Driver ABOVE board: always counter, but clamp near board
        soft_target = offer - board * step           # move down a bit
        target = float(round(min(soft_target, high_ceiling)))
        status = "counter"
    else:
        # Driver BELOW board: negotiate only if not an extreme lowball
        low_pct = (board - offer) / board if board > 0 else 1.0
        if low_pct <= NEGOTIATE_WITHIN:
            target = float(round(offer + board * step))
            status = "counter"
        else:
            target = float(round(board))
            status = "reject"

    # Enforce attempt cap AFTER deciding
    if status == "counter" and attempts >= MAX_ATTEMPTS:
        return {
            "status": "reject",
            "target_rate": float(round(board)),
            "message": "I appreciate the negotiation. We’re not aligned on rate, so I’ll have to pass this time.",
            "handoff": False,
            "final": True,
        }

    if status == "counter":
        return {
            "status": "counter",
            "target_rate": target,
            "message": f"I can do ${int(target):,}. Does that work?",
            "handoff": False,
            "final": False,
        }

    return {
        "status": "reject",
        "target_rate": float(round(board)),
        "message": "We’re too far apart on rate for this load.",
        "handoff": False,
        "final": True,
    }

def evaluate(state: NegotiationState) -> NegotiationState:
    board, offer = state["board_rate"], state["offer"]
    tries = state.get("attempts", 1)

    # Run the negotiation logic
    result = deterministic_round(board, offer, tries)

    # Ensure you return the updated attempts count
    updated_attempts = tries + 1 if result["status"] == "counter" else tries

    out = state.copy()
    out["attempts"] = updated_attempts  # increment here
    out["result"] = result
    return out

flow = StateGraph(NegotiationState, name="NegotiationSingleRound")
flow.add_node("Evaluate", evaluate)
flow.add_edge(START, "Evaluate")
flow.add_edge("Evaluate", END)
NEGOTIATION_GRAPH = flow.compile()

def run_negotiation(board_rate: float, initial_offer: float, attempts: int = 1) -> dict:
    init: NegotiationState = {
        "board_rate": float(board_rate),
        "offer": float(initial_offer),
        "attempts": int(attempts),
    }
    final_state = NEGOTIATION_GRAPH.invoke(init)
    res = final_state["result"]
    res["attempts"] = final_state["attempts"]  # fetch updated state attempts
    return res
    
