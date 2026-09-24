from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from agent.tools.k8s_graph import get_ownership
from agent.tools.prometheus import query_metrics
from agent.tools.loki import query_logs
from agent.tools.tempo import query_traces
from agent.ranking.rank import generate_hypotheses
from agent.notify.slack import send_brief
from agent.actions.argocd import rollback
from agent.actions.pagerduty import escalate
from agent.audit.log import record


class Alert(TypedDict):
    service: str
    summary: str
    severity: str


class Hypothesis(TypedDict):
    cause: str
    confidence: float
    sources: list[str]
    evidence: list[str]


class State(TypedDict):
    alert: Alert
    owner_info: dict
    metrics: dict
    logs: dict
    traces: dict
    hypotheses: list[Hypothesis]
    slack_result: dict


def fetch_ownership(state: State) -> State:
    state["owner_info"] = get_ownership(state["alert"]["service"])
    return state


def fetch_metrics(state: State) -> State:
    state["metrics"] = query_metrics(state["alert"]["service"])
    return state


def fetch_logs(state: State) -> State:
    state["logs"] = query_logs(state["alert"]["service"])
    return state


def fetch_traces(state: State) -> State:
    state["traces"] = query_traces(state["alert"]["service"])
    return state


def llm_call(state: State) -> State:
    state["hypotheses"] = generate_hypotheses(
        state["alert"],
        state["owner_info"],
        state["metrics"],
        state["logs"],
        state["traces"],
    )
    return state


def record_considered(state: State) -> State:
    record(
        {
            "type": "hypotheses_considered",
            "alert": state["alert"],
            "hypotheses": state["hypotheses"],
        }
    )
    return state


def notify_slack(state: State) -> State:
    state["slack_result"] = send_brief(state["alert"], state["hypotheses"])
    return state


def route_after_ownership(state: State) -> str:
    if state["alert"]["severity"] == "critical":
        return "llm_call"
    return "fetch_metrics"


def execute_approved_action(
    action: str, service: str, top_cause: Optional[str]
) -> dict:
    if action == "approve_rollback":
        action_name = "argocd_rollback"
        result = rollback(service)
    elif action == "escalate":
        action_name = "pagerduty_escalate"
        result = escalate(
            summary=f"Escalating {service}: {top_cause or 'unspecified cause'}",
            dedup_key=service,
        )
    else:
        action_name = action
        result = {"error": f"unknown action: {action}"}

    record(
        {
            "type": "action_executed",
            "action": action_name,
            "service": service,
            "result": result,
        }
    )
    return result


def build_graph():
    graph = StateGraph(State)

    graph.add_node("fetch_ownership", fetch_ownership)
    graph.add_node("fetch_metrics", fetch_metrics)
    graph.add_node("fetch_logs", fetch_logs)
    graph.add_node("fetch_traces", fetch_traces)
    graph.add_node("llm_call", llm_call)
    graph.add_node("record_considered", record_considered)
    graph.add_node("notify_slack", notify_slack)

    graph.add_edge(START, "fetch_ownership")
    graph.add_edge("fetch_ownership", "fetch_metrics")
    graph.add_edge("fetch_metrics", "fetch_logs")
    graph.add_edge("fetch_logs", "fetch_traces")
    graph.add_edge("fetch_traces", "llm_call")
    graph.add_edge("llm_call", "record_considered")
    graph.add_edge("record_considered", "notify_slack")
    graph.add_edge("notify_slack", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    result = app.invoke(
        {
            "alert": {
                "service": "checkout-api",
                "summary": "p99 latency > 2s for 5m",
                "severity": "page",
            }
        }
    )
    for h in result["hypotheses"]:
        print(h)
