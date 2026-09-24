from agent.llm_client import fetch_hypotheses


def generate_hypotheses(
    alert: dict, owner_info: dict, metrics: dict, logs: dict, traces: dict
) -> list[dict]:
    hypotheses = fetch_hypotheses(alert, owner_info, metrics, logs, traces)

    ranked = []
    for h in hypotheses:
        # more independently corroborating sources raises the weight even at equal LLM confidence
        weighted_confidence = h.confidence * (0.5 + 0.5 * min(len(h.sources), 3) / 3)
        weighted_confidence = max(0.0, min(1.0, weighted_confidence))
        ranked.append(
            {
                "cause": h.cause,
                "confidence": weighted_confidence,
                "sources": h.sources,
                "evidence": [h.evidence],
            }
        )

    return sorted(ranked, key=lambda h: h["confidence"], reverse=True)
