import os
import time

import requests


def query_traces(service: str, window_minutes: int = 15) -> dict:
    base_url = os.environ.get("TEMPO_URL", "http://localhost:3200")

    end = int(time.time())
    start = end - window_minutes * 60

    params = {
        "tags": f"service.name={service}",
        "start": start,
        "end": end,
        "limit": 20,
    }

    try:
        response = requests.get(f"{base_url}/api/search", params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {"error": str(exc)}

    traces = data.get("traces") or []

    spans = []
    for trace in traces:
        duration_ms = trace.get("durationMs")
        if duration_ms is None:
            # some Tempo versions report duration in nanoseconds under durationNano
            duration_nano = trace.get("durationNano")
            duration_ms = duration_nano / 1e6 if duration_nano is not None else 0.0

        name = trace.get("rootServiceName") or trace.get("rootTraceName") or ""

        spans.append(
            {
                "trace_id": trace.get("traceID", ""),
                "duration_ms": float(duration_ms),
                "name": name,
            }
        )

    spans.sort(key=lambda s: s["duration_ms"], reverse=True)

    return {"slow_spans": spans[:5]}
