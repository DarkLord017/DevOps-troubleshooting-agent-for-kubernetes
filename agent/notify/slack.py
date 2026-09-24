import json
import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import (
    ActionsBlock,
    ButtonElement,
    DividerBlock,
    HeaderBlock,
    MarkdownTextObject,
    PlainTextObject,
    SectionBlock,
)


def send_brief(alert: dict, hypotheses: list[dict]) -> dict:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        return {"error": "SLACK_BOT_TOKEN environment variable is required"}

    channel = os.environ.get("SLACK_CHANNEL", "#incidents")
    top_cause = hypotheses[0]["cause"] if hypotheses else None

    blocks = [
        HeaderBlock(
            text=PlainTextObject(text=f"[{alert['severity'].upper()}] {alert['service']}")
        ),
        SectionBlock(text=MarkdownTextObject(text=alert["summary"])),
        DividerBlock(),
    ]

    if hypotheses:
        for h in hypotheses[:3]:
            confidence_pct = round(h["confidence"] * 100)
            sources = ", ".join(h.get("sources", [])) or "none"
            evidence = "; ".join(h.get("evidence", [])) or "none"
            blocks.append(
                SectionBlock(
                    text=MarkdownTextObject(
                        text=(
                            f"*{h['cause']}* — {confidence_pct}% confidence\n"
                            f"Sources: {sources}\n"
                            f"Evidence: {evidence}"
                        )
                    )
                )
            )
    else:
        blocks.append(SectionBlock(text=MarkdownTextObject(text="no hypotheses generated")))

    button_value = json.dumps({"service": alert["service"], "top_cause": top_cause})

    blocks.append(
        ActionsBlock(
            elements=[
                ButtonElement(
                    text=PlainTextObject(text="Approve rollback"),
                    action_id="approve_rollback",
                    value=button_value,
                ),
                ButtonElement(
                    text=PlainTextObject(text="Escalate"),
                    action_id="escalate",
                    value=button_value,
                ),
            ]
        )
    )

    client = WebClient(token=token, timeout=5)
    try:
        response = client.chat_postMessage(
            channel=channel, blocks=blocks, text=alert["summary"]
        )
    except SlackApiError as exc:
        return {"error": exc.response.get("error", str(exc))}
    except Exception as exc:
        return {"error": str(exc)}

    return {"ok": True, "channel": response.get("channel"), "ts": response.get("ts")}
