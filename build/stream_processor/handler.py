import os
import json
import boto3
from datetime import datetime, timezone

TABLE_NAME = os.getenv("TABLE_NAME", "GlobalCatalog")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
    """
    DynamoDB Streams → Lambda
    - Logs changes
    - (Placeholder) When we see an Inventory item, recompute merged_qty
    """
    # NOTE: This is a placeholder for presentation; safe no-ops beyond logging.
    # We'll replace with CRDT merge + materializations in the next steps.
    print("Received event with {} records".format(len(event.get("Records", []))))
    for rec in event.get("Records", []):
        ev = rec.get("eventName")
        src = rec.get("eventSourceARN", "")
        keys = rec.get("dynamodb", {}).get("Keys", {})
        print(f"[{ev}] {keys} source={src}")

    # Example: write a heartbeat row to prove the stream processor is alive
    try:
        table.put_item(
            Item={
                "PK": "SYSTEM#STREAM",
                "SK": f"HEARTBEAT#{datetime.now(timezone.utc).isoformat()}",
                "component": "stream_processor",
                "status": "ok"
            }
        )
    except Exception as e:
        print("Heartbeat write failed:", repr(e))

    return {"ok": True}
