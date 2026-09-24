import os

import requests


def rollback(application: str) -> dict:
    server = os.environ.get("ARGOCD_SERVER", "https://localhost:8080")
    token = os.environ.get("ARGOCD_TOKEN")
    if not token:
        return {"error": "ARGOCD_TOKEN is not set"}

    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.get(
            f"{server}/api/v1/applications/{application}",
            headers=headers,
            timeout=5,
        )
        if resp.status_code >= 300:
            return {"error": f"failed to fetch application: HTTP {resp.status_code}"}

        history = resp.json().get("status", {}).get("history", [])
        if len(history) < 2:
            return {"error": "no prior revision to roll back to"}

        # last entry is the currently deployed (bad) revision; the one before it is the rollback target
        target = history[-2]

        rollback_resp = requests.post(
            f"{server}/api/v1/applications/{application}/rollback",
            headers=headers,
            json={"id": target["id"]},
            timeout=5,
        )
        if rollback_resp.status_code >= 300:
            return {"error": f"rollback failed: HTTP {rollback_resp.status_code}"}

        return {
            "ok": True,
            "application": application,
            "rolled_back_to": target.get("revision", target["id"]),
        }
    except Exception as e:
        return {"error": str(e)}
