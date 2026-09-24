import os
import time

import requests


def query_logs(service: str, window_minutes: int = 15) -> dict:
    loki_url = os.environ.get("LOKI_URL", "http://localhost:3100")
    end_ns = time.time_ns()
    start_ns = end_ns - window_minutes * 60 * 1_000_000_000

    query = f'{{service="{service}"}} |~ "(?i)error|exception|fail"'

    try:
        response = requests.get(
            f"{loki_url}/loki/api/v1/query_range",
            params={
                "query": query,
                "start": start_ns,
                "end": end_ns,
                "limit": 50,
            },
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()

        entries: list[tuple[str, str]] = []
        for result in data.get("data", {}).get("result", []):
            for ts, line in result.get("values", []):
                entries.append((ts, line))

        entries.sort(key=lambda e: int(e[0]))
        return {"error_lines": [line for _, line in entries[-50:]]}
    except Exception as e:
        return {"error": str(e)}
