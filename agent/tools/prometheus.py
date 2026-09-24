import os
import time

import requests

QUERIES = {
    "error_rate": 'rate(http_requests_total{{service="{service}", status=~"5.."}}[5m])',
    "latency_p99": 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m]))',
    "cpu": 'rate(container_cpu_usage_seconds_total{{service="{service}"}}[5m])',
}


def _latest_value(result: dict):
    series = result.get("data", {}).get("result", [])
    if not series:
        return None
    values = series[0].get("values", [])
    if not values:
        return None
    return float(values[-1][1])


def query_metrics(service: str, window_minutes: int = 15) -> dict:
    prometheus_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
    end = time.time()
    start = end - window_minutes * 60
    metrics: dict = {}
    try:
        for name, template in QUERIES.items():
            resp = requests.get(
                f"{prometheus_url}/api/v1/query_range",
                params={
                    "query": template.format(service=service),
                    "start": start,
                    "end": end,
                    "step": "60s",
                },
                timeout=5,
            )
            resp.raise_for_status()
            metrics[name] = _latest_value(resp.json())
    except Exception as exc:
        return {"error": str(exc)}
    return metrics
