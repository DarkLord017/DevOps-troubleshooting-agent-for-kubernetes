import os
from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class Hypothesis(BaseModel):
    cause: str
    confidence: float = Field(ge=0, le=1)
    sources: list[Literal["ownership", "metrics", "logs", "traces"]]
    evidence: str


class HypothesesResponse(BaseModel):
    hypotheses: list[Hypothesis]


def fetch_hypotheses(
    alert: dict, owner_info: dict, metrics: dict, logs: dict, traces: dict
) -> list[Hypothesis]:
    llm = ChatOpenAI(
        model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"),
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    ).with_structured_output(HypothesesResponse)

    prompt = (
        "You are a root-cause analysis agent for on-call incident response.\n"
        f"Alert: {alert}\n"
        f"Ownership: {owner_info}\n"
        f"Metrics (last 15m): {metrics}\n"
        f"Logs: {logs}\n"
        f"Traces: {traces}\n\n"
        "Identify the top 3 candidate root causes, ranked by your confidence, "
        "each citing which data sources support it and the specific evidence."
    )

    try:
        response = llm.invoke(prompt)
    except Exception:
        return []

    return response.hypotheses
