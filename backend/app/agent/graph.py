from __future__ import annotations

import sqlite3
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class MigrationGraphState(TypedDict):
    batch_id: str
    proposal: dict[str, Any]
    policy: str
    decision: dict[str, Any] | None


def policy_gate(state: MigrationGraphState) -> MigrationGraphState:
    return state


def human_mapping_review(state: MigrationGraphState) -> MigrationGraphState:
    decision = interrupt(
        {
            "batch_id": state["batch_id"],
            "proposal": state["proposal"],
            "allowed_actions": ["APPROVE", "CORRECT", "REJECT"],
        }
    )
    return {**state, "decision": decision}


def route_policy(state: MigrationGraphState) -> str:
    return "apply" if state["policy"] == "AUTO_APPLY" else "review"


def apply_mapping(state: MigrationGraphState) -> MigrationGraphState:
    return state


def build_graph(connection: sqlite3.Connection):
    graph = StateGraph(MigrationGraphState)
    graph.add_node("policy_gate", policy_gate)
    graph.add_node("human_mapping_review", human_mapping_review)
    graph.add_node("apply_mapping", apply_mapping)
    graph.add_edge(START, "policy_gate")
    graph.add_conditional_edges("policy_gate", route_policy, {"apply": "apply_mapping", "review": "human_mapping_review"})
    graph.add_edge("human_mapping_review", "apply_mapping")
    graph.add_edge("apply_mapping", END)
    return graph.compile(checkpointer=SqliteSaver(connection))


__all__ = ["Command", "MigrationGraphState", "build_graph"]

