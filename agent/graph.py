import os
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from agent.tools.k8s_graph import get_ownership
from agent.tools.prometheus import query_metrics
from agent.tools.loki import query_logs
from agent.tools.tempo import query_traces


class Alert(TypedDict):
    service: str
    summary: str
    severity: str


class Hypothesis(TypedDict):
    cause: str
    confidence: float
    evidence: list[str]


class State(TypedDict):
    alert: Alert
    owner_info: dict
    metrics: dict
    logs: dict
    traces: dict
    hypotheses: list[Hypothesis]


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


def rank_hypotheses(state: State) -> State:
    llm = ChatOpenAI(
        model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"),
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
    prompt = (
        "You are a root-cause analysis agent for on-call incident response.\n"
        f"Alert: {state['alert']}\n"
        f"Ownership: {state['owner_info']}\n"
        f"Metrics (last 15m): {state['metrics']}\n"
        f"Logs: {state['logs']}\n"
        f"Traces: {state['traces']}\n\n"
        "List the top 3 candidate root causes ranked by confidence, one per line, "
        "each as: cause | confidence(0-1) | supporting evidence"
    )
    response = llm.invoke(prompt)

    hypotheses: list[Hypothesis] = []
    for line in response.content.strip().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3:
            cause, confidence, evidence = parts
            try:
                confidence_val = float(confidence)
            except ValueError:
                confidence_val = 0.0
            hypotheses.append(
                {"cause": cause, "confidence": confidence_val, "evidence": [evidence]}
            )

    state["hypotheses"] = sorted(
        hypotheses, key=lambda h: h["confidence"], reverse=True
    )
    return state


def route_after_ownership(state: State) -> str:
    if state["alert"]["severity"] == "critical":
        return "rank_hypotheses"
    return "fetch_metrics"


def build_graph():
    graph = StateGraph(State)

    graph.add_node("fetch_ownership", fetch_ownership)
    graph.add_node("fetch_metrics", fetch_metrics)
    graph.add_node("fetch_logs", fetch_logs)
    graph.add_node("fetch_traces", fetch_traces)
    graph.add_node("rank_hypotheses", rank_hypotheses)

    graph.add_edge(START, "fetch_ownership")
    graph.add_edge("fetch_ownership", "fetch_metrics")
    graph.add_edge("fetch_metrics", "fetch_logs")
    graph.add_edge("fetch_logs", "fetch_traces")
    graph.add_edge("fetch_traces", "rank_hypotheses")
    graph.add_edge("rank_hypotheses", END)

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
