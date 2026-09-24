import os

import requests


def escalate(summary: str, dedup_key: str) -> dict:
    routing_key = os.environ.get("PAGERDUTY_ROUTING_KEY")
    if not routing_key:
        return {"error": "PAGERDUTY_ROUTING_KEY is not set"}

    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": dedup_key,
        "payload": {
            "summary": summary,
            "source": "rca-agent",
            "severity": "critical",
        },
    }

    try:
        resp = requests.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload,
            timeout=5,
        )
        if resp.status_code >= 300:
            return {"error": f"escalation failed: HTTP {resp.status_code}"}

        return {"ok": True, "dedup_key": resp.json().get("dedup_key", dedup_key)}
    except Exception as e:
        return {"error": str(e)}
