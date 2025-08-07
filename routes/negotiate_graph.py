# """
# routes/negotiate_graph.py
# ───────────────────────────────────────────────────────────────────────────────
# Negotiation rules:
# - Accept if |offer - board| <= ACCEPT_WITHIN * board  → handoff to human
# - Counter if within NEGOTIATE_WITHIN * board         → up to MAX_ATTEMPTS
# - Reject otherwise or if attempts hit MAX_ATTEMPTS
# """

# from __future__ import annotations

# import json
# import os
# from typing import Literal, TypedDict

# from dotenv import load_dotenv
# from langgraph.graph import END, START, StateGraph
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_openai import ChatOpenAI

# # ────────────────────────────── ENV / LLM SETUP ──────────────────────────────
# load_dotenv()
# OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# USE_LLM = bool(OPENAI_KEY)  # Toggle automatically

# if USE_LLM:
#     LLM = ChatOpenAI(
#         model="gpt-4o-mini",
#         api_key=OPENAI_KEY,
#         temperature=0.2,
#     )

# # ──────────────────────────── BUSINESS CONSTANTS ─────────────────────────────
# MAX_MARGIN = 0.15        # accept if ≤ 15 % below board rate
# MAX_COUNTER_DIFF = 0.30  # counter if ≤ 30 % below board rate
# COUNTER_STEP = 0.05       # counter = offer + 5 % × board_rate
# MAX_ATTEMPTS = 3          # hard stop after 3 rounds

# # ───────────────────────────── STATE SCHEMA ──────────────────────────────────
# class NegotiationState(TypedDict, total=False):
#     board_rate: int
#     offer: float
#     attempts: int
#     result: dict   # {"status": str, "target_rate": float, "message": str}

# # ───────────────────────── LLM PROMPT TEMPLATE ───────────────────────────────
# SYSTEM_PROMPT = """
# You are an expert freight broker negotiating spot-market rates.

# • Board (posted) rate ............... {board_rate}
# • Driver’s current offer ............ {offer}
# • All money values are whole US dollars (no cents).

# Decision rules
# - accept if offer is ≤ 15% below the board rate
# - counter (offer + 5% * board) if >15% and ≤30% below board
# - reject if >30% below board

# Return **ONLY valid JSON** with keys: status, target_rate, message.
# """

# PROMPT = ChatPromptTemplate.from_messages(
#     [
#         ("system", SYSTEM_PROMPT),
#         ("human", "Board rate: {board_rate}  \nCurrent offer: {offer}"),
#     ]
# )

# # ─────────────────── HELPER – ONE LLM NEGOTIATION ROUND ──────────────────────
# def llm_round(board_rate: int, offer: float) -> dict:
#     """
#     Ask the LLM to evaluate a single negotiation round.
#     Returns a JSON-dict or raises ValueError on bad JSON.
#     """
#     messages = PROMPT.format_messages(board_rate=board_rate, offer=offer)
#     resp = LLM.invoke(messages)  # type: ignore[arg-type]  (depends on SDK)

#     text = resp.content if hasattr(resp, "content") else str(resp)
#     try:
#         return json.loads(text)
#     except Exception as exc:
#         raise ValueError(f"LLM returned non-JSON: {text!r}") from exc

# # ───────────────────── RULE-BASED FALLBACK ROUND ─────────────────────────────
# def deterministic_round(board_rate: int, offer: float, tries: int) -> dict:
#     """Simple math fallback if no LLM key or parsing error."""
#     diff = (board_rate - offer) / board_rate

#     # Accept
#     if diff <= MAX_MARGIN:
#         return {
#             "status": "accept",
#             "target_rate": offer,
#             "message": f"Understood. We can confirm at ${offer:,.0f}.",
#         }

#     # Counter
#     if diff <= MAX_COUNTER_DIFF and tries < MAX_ATTEMPTS:
#         tgt = round(offer + board_rate * COUNTER_STEP)
#         return {
#             "status": "counter",
#             "target_rate": round(tgt, 2),
#             "message": f"I can do ${tgt:,.0f}. Does that work?",
#         }

#     # Reject
#     return {
#         "status": "reject",
#         "target_rate": board_rate,
#         "message": "We’re too far apart on rate for this load.",
#     }

# # ────────────────────────── GRAPH NODE LOGIC ─────────────────────────────────
# def evaluate(state: NegotiationState) -> NegotiationState:
#     """
#     Graph node: run one negotiation round (LLM or deterministic),
#     then update the NegotiationState.
#     """
#     board, offer, tries = state["board_rate"], state["offer"], state["attempts"]

#     try:
#         result = llm_round(board, offer) if USE_LLM else None
#     except Exception:
#         result = None  # fallback to deterministic

#     if not result:
#         result = deterministic_round(board, offer, tries)

#     # Ensure the JSON always contains a numeric target_rate
#     if result.get("target_rate") is None:
#         if result["status"] == "accept":
#             result["target_rate"] = offer          # accepted at caller’s price
#         else:  # "counter" or "reject" missing a rate → use board_rate
#             result["target_rate"] = board
#     # (optional) coerce to float to satisfy Pydantic strictly
#     result["target_rate"] = float(result["target_rate"])
#     result["attempts"] = tries

#     out = state.copy()
#     out["result"] = result
#     return out

# # def router(state: NegotiationState) -> Literal["accept", "reject", "counter"]:
# #     """Direct LangGraph edge based on result status & attempt cap."""
# #     status, attempts = state["result"]["status"], state["attempts"]
# #     if status == "counter" and attempts > MAX_ATTEMPTS:
# #         return "reject"
# #     return status

# # # ────────────────────────── BUILD THE LANGGRAPH ──────────────────────────────
# # flow = StateGraph(NegotiationState, name="AgenticNegotiation")
# # flow.add_node("Evaluate", evaluate)
# # flow.add_edge(START, "Evaluate")
# # flow.add_conditional_edges(
# #     "Evaluate",
# #     router,
# #     {"accept": END, "reject": END, "counter": "Evaluate"},
# # )
# # NEGOTIATION_GRAPH = flow.compile()

# flow = StateGraph(NegotiationState, name="NegotiationSingleRound")
# flow.add_node("Evaluate", evaluate)
# flow.add_edge(START, "Evaluate")
# flow.add_edge("Evaluate", END)
# NEGOTIATION_GRAPH = flow.compile()
# # ───────────────────────── PUBLIC RUNNER FUNC ────────────────────────────────
# def run_negotiation(
#     board_rate: int,
#     initial_offer: float,
#     attempts: int = 1,
# ) -> dict:
#     """
#     High-level helper for FastAPI route.

#     Parameters
#     ----------
#     board_rate : int
#         Posted rate for the load.
#     initial_offer : float
#         Carrier’s first offer.
#     attempts : int, default 1
#         Current negotiation round (1-based).

#     Returns
#     -------
#     dict
#         {"status": str, "target_rate": float, "message": str}
#     """
#     init: NegotiationState = {
#         "board_rate": board_rate,
#         "offer": initial_offer,
#         "attempts": attempts,
#     }
#     final_state = NEGOTIATION_GRAPH.invoke(init)
#     return final_state["result"]

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
    
