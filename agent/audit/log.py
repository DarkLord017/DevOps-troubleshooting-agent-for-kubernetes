import json
import os
import sys
from datetime import datetime, timezone


def record(event: dict) -> None:
    event = dict(event)
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    path = os.environ.get("AUDIT_LOG_PATH", "audit.log")
    try:
        with open(path, "a") as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
    except Exception as exc:
        print(f"audit log write failed: {exc}", file=sys.stderr)
