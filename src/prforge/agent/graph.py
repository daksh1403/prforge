"""Build the LangGraph state machine for PRForge.

    START -> fetch_issue -> clone_and_map -> localize -> plan -> edit -> test
                ^                                                        |
                |_______ (tests fail & iterations left) __________________|
                                                                         v
                                                                      review -> push_and_pr -> END
                                                                         |
                                                                    (rejected) -> END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from prforge.agent.nodes import Agent
from prforge.agent.state import RunState


def build_graph(agent: Agent):
    g = StateGraph(RunState)

    g.add_node("fetch_issue", agent.fetch_issue)
    g.add_node("clone_and_map", agent.clone_and_map)
    g.add_node("localize", agent.localize)
    g.add_node("plan", agent.plan)
    g.add_node("edit", agent.edit)
    g.add_node("test", agent.test)
    g.add_node("review", agent.review)
    g.add_node("push_and_pr", agent.push_and_pr)

    g.add_edge(START, "fetch_issue")
    g.add_edge("fetch_issue", "clone_and_map")
    g.add_edge("clone_and_map", "localize")
    g.add_edge("localize", "plan")
    g.add_edge("plan", "edit")
    g.add_edge("edit", "test")
    g.add_conditional_edges(
        "test",
        agent.route_after_test,
        {"edit": "edit", "review": "review"},
    )
    g.add_conditional_edges(
        "review",
        agent.route_after_review,
        {"push_and_pr": "push_and_pr", END: END},
    )
    g.add_edge("push_and_pr", END)

    return g.compile()
