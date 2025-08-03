"""
routes/negotiate_graph.py  ────────────────────────────────────────────────────
LangGraph state-machine that negotiates up to three rounds.

State schema (NegotiationState)
────────────────────────────────
board_rate : int        # reference rate from CSV
offer      : float      # carrier's current offer
attempts   : int        # 1-based counter round
result     : dict       # populated each round → {"status", "target_rate", "message"}

Public helper
─────────────
run_negotiation(board_rate: int, initial_offer: float, attempts: int = 1) -> dict
"""

from __future__ import annotations

from typing import Literal, TypedDict
from langgraph.graph import StateGraph, END

# ── Business constants ────────────────────────────────────────────────────────
MAX_MARGIN       = 0.15   # accept if ≤ 15 % below board
MAX_COUNTER_DIFF = 0.30   # counter if ≤ 30 % below board
COUNTER_STEP     = 0.05   # counter = offer + 5 % of board
MAX_ATTEMPTS     = 3      # hard stop after 3 rounds

# ── State definition for type-safety ──────────────────────────────────────────
class NegotiationState(TypedDict, total=False):
    board_rate: int
    offer: float
    attempts: int
    result: dict   # {"status": str, "target_rate": float, "message": str}

# ── Graph node: evaluate a single round ───────────────────────────────────────
def evaluate_round(state: NegotiationState) -> NegotiationState:
    board  = state["board_rate"]
    offer  = state["offer"]
    tries  = state["attempts"]

    diff   = board - offer
    rel    = diff / board                                       # >0 when offer below board

    # ----- decide outcome -----------------------------------------------------
    if rel <= MAX_MARGIN:
        status, tgt, msg = "accept", offer, f"Great – confirmed at ${offer:.0f}!"
    elif rel <= MAX_COUNTER_DIFF and tries < MAX_ATTEMPTS:
        tgt   = offer + board * COUNTER_STEP
        status, msg = "counter", f"The best I can do is ${tgt:.0f}. Does that work?"
    else:
        status, tgt, msg = "reject", board, "Sorry, we’re too far off the board rate."

    # ----- build next state ---------------------------------------------------
    next_state = state.copy()
    next_state["result"] = {"status": status, "target_rate": round(tgt, 2), "message": msg}

    if status == "counter":
        next_state["offer"]    = tgt
        next_state["attempts"] = tries + 1

    return next_state

# ── Router: choose where to go next ───────────────────────────────────────────
def choose_edge(state: NegotiationState) -> Literal["counter", "accept", "reject"]:
    status   = state["result"]["status"]
    attempts = state["attempts"]

    # force rejection if counters exceeded
    if status == "counter" and attempts > MAX_ATTEMPTS:
        return "reject"
    return status  # "accept" | "counter" | "reject"

# ── Compile LangGraph ────────────────────────────────────────────────────────
graph = StateGraph(NegotiationState, name="NegotiationGraph")
graph.add_node("Evaluate", evaluate_round)
graph.add_conditional_edges(
    "Evaluate",
    choose_edge,
    {
        "accept": END,
        "reject": END,
        "counter": "Evaluate",  # loop
    },
)
graph.set_entry_point("Evaluate")
NEGOTIATION_GRAPH = graph.compile()

# ── Public helper -------------------------------------------------------------
def run_negotiation(board_rate: int, initial_offer: float, attempts: int = 1) -> dict:
    """
    Args:
        board_rate    – Load’s listed rate
        initial_offer – Carrier’s first offer
        attempts      – Current attempt count (1-based when called)

    Returns:
        dict(status, target_rate, message)
    """
    init_state: NegotiationState = {
        "board_rate": board_rate,
        "offer":       initial_offer,
        "attempts":    attempts,
        "result":      {},
    }
    final_state = NEGOTIATION_GRAPH.invoke(init_state)
    return final_state["result"]
