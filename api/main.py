import hashlib
import hmac
import json
import os
import time

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from agent.graph import build_graph, execute_approved_action

app = FastAPI()
_graph = build_graph()


def parse_alertmanager(payload: dict) -> dict:
    alerts = payload.get("alerts", [])
    labels = alerts[0].get("labels", {}) if alerts else payload.get("commonLabels", {})
    annotations = (
        alerts[0].get("annotations", {}) if alerts else payload.get("commonAnnotations", {})
    )
    return {
        "service": labels.get("service") or labels.get("alertname", "unknown"),
        "summary": annotations.get("summary") or annotations.get("description", "no summary"),
        "severity": labels.get("severity", "warning"),
    }


def parse_pagerduty(payload: dict) -> dict:
    data = payload.get("event", {}).get("data", {})
    urgency = data.get("urgency", "low")
    return {
        "service": data.get("service", {}).get("summary", "unknown"),
        "summary": data.get("title", "no summary"),
        "severity": "critical" if urgency == "high" else "warning",
    }


def parse_alert_payload(payload: dict) -> dict:
    if isinstance(payload.get("event"), dict):
        return parse_pagerduty(payload)
    return parse_alertmanager(payload)


def run_alert_pipeline(alert: dict) -> None:
    _graph.invoke({"alert": alert})


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    secret = os.environ.get("SLACK_SIGNING_SECRET")
    if not secret or not timestamp or not signature:
        return False
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
    basestring = f"v0:{timestamp}:{body.decode()}"
    computed = "v0=" + hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


@app.post("/alert")
async def receive_alert(request: Request, background_tasks: BackgroundTasks):
    expected_token = os.environ.get("ALERT_WEBHOOK_TOKEN")
    if expected_token and request.headers.get("X-Webhook-Token") != expected_token:
        raise HTTPException(status_code=401, detail="invalid webhook token")

    payload = await request.json()
    alert = parse_alert_payload(payload)
    background_tasks.add_task(run_alert_pipeline, alert)
    return {"ok": True, "alert": alert}


@app.post("/slack/interactivity")
async def slack_interactivity(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="invalid slack signature")

    form = await request.form()
    payload = json.loads(form["payload"])
    action = payload["actions"][0]
    value = json.loads(action["value"])

    background_tasks.add_task(
        execute_approved_action,
        action=action["action_id"],
        service=value["service"],
        top_cause=value.get("top_cause"),
    )
    return {"ok": True}
