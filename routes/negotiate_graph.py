"""
routes/negotiate_graph.py
───────────────────────────────────────────────────────────────────────────────
Agentic, LangGraph-driven negotiation engine.

• Supports up to three back-and-forth rounds.
• Uses an OpenAI chat model when an `OPENAI_API_KEY` is available; otherwise
  falls back to a deterministic rule-based decision function.
• Designed to be called from routes/negotiate.py:

      from routes.negotiate_graph import run_negotiation
      result = run_negotiation(board_rate=2300, initial_offer=2000, attempts=1)

Return value:

    {
        "status": "accept" | "counter" | "reject",
        "target_rate": 2175,
        "message": "Best I can do is $2 175. Does that work?"
    }
"""

from __future__ import annotations

import json
import os
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# ────────────────────────────── ENV / LLM SETUP ──────────────────────────────
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

USE_LLM = bool(OPENAI_KEY)  # Toggle automatically

if USE_LLM:
    LLM = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=OPENAI_KEY,
        temperature=0.2,
    )

# ──────────────────────────── BUSINESS CONSTANTS ─────────────────────────────
MAX_MARGIN = 0.15        # accept if ≤ 15 % below board rate
MAX_COUNTER_DIFF = 0.30  # counter if ≤ 30 % below board rate
COUNTER_STEP = 0.05       # counter = offer + 5 % × board_rate
MAX_ATTEMPTS = 3          # hard stop after 3 rounds

# ───────────────────────────── STATE SCHEMA ──────────────────────────────────
class NegotiationState(TypedDict, total=False):
    board_rate: int
    offer: float
    attempts: int
    result: dict   # {"status": str, "target_rate": float, "message": str}

# ───────────────────────── LLM PROMPT TEMPLATE ───────────────────────────────
SYSTEM_PROMPT = """
You are an expert freight broker negotiating spot-market rates.

• Board (posted) rate ............... {board_rate}
• Driver’s current offer ............ {offer}
• All money values are whole US dollars (no cents).

Decision rules
- accept if offer is ≤ 15% below the board rate
- counter (offer + 5% * board) if >15% and ≤30% below board
- reject if >30% below board

Return **ONLY valid JSON** with keys: status, target_rate, message.
"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Board rate: {board_rate}  \nCurrent offer: {offer}"),
    ]
)

# ─────────────────── HELPER – ONE LLM NEGOTIATION ROUND ──────────────────────
def llm_round(board_rate: int, offer: float) -> dict:
    """
    Ask the LLM to evaluate a single negotiation round.
    Returns a JSON-dict or raises ValueError on bad JSON.
    """
    messages = PROMPT.format_messages(board_rate=board_rate, offer=offer)
    resp = LLM.invoke(messages)  # type: ignore[arg-type]  (depends on SDK)

    text = resp.content if hasattr(resp, "content") else str(resp)
    try:
        return json.loads(text)
    except Exception as exc:
        raise ValueError(f"LLM returned non-JSON: {text!r}") from exc

# ───────────────────── RULE-BASED FALLBACK ROUND ─────────────────────────────
def deterministic_round(board_rate: int, offer: float, tries: int) -> dict:
    """Simple math fallback if no LLM key or parsing error."""
    diff = (board_rate - offer) / board_rate

    # Accept
    if diff <= MAX_MARGIN:
        return {
            "status": "accept",
            "target_rate": offer,
            "message": f"Understood. We can confirm at ${offer:,.0f}.",
        }

    # Counter
    if diff <= MAX_COUNTER_DIFF and tries < MAX_ATTEMPTS:
        tgt = round(offer + board_rate * COUNTER_STEP)
        return {
            "status": "counter",
            "target_rate": round(tgt, 2),
            "message": f"I can do ${tgt:,.0f}. Does that work?",
        }

    # Reject
    return {
        "status": "reject",
        "target_rate": board_rate,
        "message": "We’re too far apart on rate for this load.",
    }

# ────────────────────────── GRAPH NODE LOGIC ─────────────────────────────────
def evaluate(state: NegotiationState) -> NegotiationState:
    """
    Graph node: run one negotiation round (LLM or deterministic),
    then update the NegotiationState.
    """
    board, offer, tries = state["board_rate"], state["offer"], state["attempts"]

    try:
        result = llm_round(board, offer) if USE_LLM else None
    except Exception:
        result = None  # fallback to deterministic

    if not result:
        result = deterministic_round(board, offer, tries)

    # Ensure the JSON always contains a numeric target_rate
    if result.get("target_rate") is None:
        if result["status"] == "accept":
            result["target_rate"] = offer          # accepted at caller’s price
        else:  # "counter" or "reject" missing a rate → use board_rate
            result["target_rate"] = board
    # (optional) coerce to float to satisfy Pydantic strictly
    result["target_rate"] = float(result["target_rate"])
    result["attempts"] = tries

    out = state.copy()
    out["result"] = result
    return out

# def router(state: NegotiationState) -> Literal["accept", "reject", "counter"]:
#     """Direct LangGraph edge based on result status & attempt cap."""
#     status, attempts = state["result"]["status"], state["attempts"]
#     if status == "counter" and attempts > MAX_ATTEMPTS:
#         return "reject"
#     return status

# # ────────────────────────── BUILD THE LANGGRAPH ──────────────────────────────
# flow = StateGraph(NegotiationState, name="AgenticNegotiation")
# flow.add_node("Evaluate", evaluate)
# flow.add_edge(START, "Evaluate")
# flow.add_conditional_edges(
#     "Evaluate",
#     router,
#     {"accept": END, "reject": END, "counter": "Evaluate"},
# )
# NEGOTIATION_GRAPH = flow.compile()

flow = StateGraph(NegotiationState, name="NegotiationSingleRound")
flow.add_node("Evaluate", evaluate)
flow.add_edge(START, "Evaluate")
flow.add_edge("Evaluate", END)
NEGOTIATION_GRAPH = flow.compile()
# ───────────────────────── PUBLIC RUNNER FUNC ────────────────────────────────
def run_negotiation(
    board_rate: int,
    initial_offer: float,
    attempts: int = 1,
) -> dict:
    """
    High-level helper for FastAPI route.

    Parameters
    ----------
    board_rate : int
        Posted rate for the load.
    initial_offer : float
        Carrier’s first offer.
    attempts : int, default 1
        Current negotiation round (1-based).

    Returns
    -------
    dict
        {"status": str, "target_rate": float, "message": str}
    """
    init: NegotiationState = {
        "board_rate": board_rate,
        "offer": initial_offer,
        "attempts": attempts,
    }
    final_state = NEGOTIATION_GRAPH.invoke(init)
    return final_state["result"]
