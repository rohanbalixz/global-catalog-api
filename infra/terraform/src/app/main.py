from fastapi import FastAPI
from pydantic import BaseModel
import os

app = FastAPI(title="Global Catalog API", version="0.1.0")

HOME_REGION = os.getenv("HOME_REGION", "us-east-1")
READ_CONSISTENCY = os.getenv("READ_CONSISTENCY", "strong-local")  # strong-local | eventual-global

class Health(BaseModel):
    status: str
    region: str

@app.get("/health", response_model=Health)
def health():
    return Health(status="ok", region=HOME_REGION)

@app.get("/explain-consistency")
def explain_consistency():
    """
    Returns a plain-English explanation of the read/write consistency policy in effect.
    (We’ll wire this to actual code paths next.)
    """
    if READ_CONSISTENCY == "strong-local":
        note = "Local region reads are strongly consistent; cross-region reads are eventual."
    else:
        note = "All reads are eventual for lower latency; local writes still ack locally."
    return {
        "policy": READ_CONSISTENCY,
        "note": note,
        "how_to_change": "Set READ_CONSISTENCY env to 'strong-local' or 'eventual-global'."
    }

from fastapi import HTTPException
from typing import Optional, Dict, Any
from src.lib.catalog import put_product_region, get_product_region, upsert_inventory, compute_merged_qty

class ProductIn(BaseModel):
    product_id: str
    region_code: str
    title: Optional[str] = None
    currency: Optional[str] = None
    price: Optional[float] = None
    attrs: Optional[Dict[str, Any]] = None

class InventoryIn(BaseModel):
    product_id: str
    warehouse_id: str
    region_code: str
    inc: int = 0
    dec: int = 0

@app.put("/products")
def put_product(p: ProductIn):
    payload = {
        "title": p.title,
        "currency": p.currency,
        "price": p.price,
        "attrs": p.attrs or {},
    }
    return put_product_region(p.product_id, p.region_code, payload)

@app.get("/products/{product_id}/{region_code}")
def get_product(product_id: str, region_code: str):
    res = get_product_region(product_id, region_code)
    if not res.get("found"):
        raise HTTPException(status_code=404, detail="not found")
    return res

@app.post("/inventory")
def post_inventory(body: InventoryIn):
    return upsert_inventory(body.product_id, body.warehouse_id, body.region_code, body.inc, body.dec)

from botocore.config import Config as _BotoCfg
import boto3 as _boto3, os as _os

# Lightweight Dynamo handle for inventory reads (strongly consistent)
_TABLE_NAME = _os.getenv("TABLE_NAME", "GlobalCatalog")
_HOME_REGION = _os.getenv("HOME_REGION", "us-east-1")
_dy = _boto3.resource("dynamodb", region_name=_HOME_REGION, config=_BotoCfg(retries={"max_attempts":5,"mode":"standard"}))
_inv_table = _dy.Table(_TABLE_NAME)

@app.get("/inventory/{product_id}/{warehouse_id}")
def get_inventory(product_id: str, warehouse_id: str, region: str = "us-east-1"):
    key = {"PK": f"PRODUCT#{product_id}", "SK": f"INV#{warehouse_id}#{region}"}
    resp = _inv_table.get_item(Key=key, ConsistentRead=True)
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    qty = compute_merged_qty(item)
    return {
        "product_id": product_id,
        "warehouse_id": warehouse_id,
        "region": region,
        "qty": qty,
        "raw": item
    }

@app.get("/inventory/{product_id}")
def get_inventory_global(product_id: str):
    """
    Aggregate inventory across ALL warehouses/regions for this product.
    Queries PK=PRODUCT#<id> with SK begins_with('INV#').
    """
    from boto3.dynamodb.conditions import Key
    resp = _inv_table.query(
        KeyConditionExpression=Key("PK").eq(f"PRODUCT#{product_id}") & Key("SK").begins_with("INV#"),
        ConsistentRead=True,
    )
    items = resp.get("Items", [])
    total = 0
    per_location = []
    for it in items:
        qty = compute_merged_qty(it)
        total += qty
        per_location.append({"sk": it.get("SK"), "qty": qty})
    return {"product_id": product_id, "total_qty": total, "locations": per_location}

import time
from starlette.middleware.base import BaseHTTPMiddleware

class ObservabilityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        t0 = time.perf_counter()
        resp = await call_next(request)
        resp.headers["X-Region"] = HOME_REGION
        resp.headers["X-Consistency"] = READ_CONSISTENCY
        resp.headers["X-Server-ProcessMs"] = f"{(time.perf_counter()-t0)*1000:.2f}"
        return resp

app.add_middleware(ObservabilityHeaders)

from datetime import datetime, timezone
from decimal import Decimal
import json as _json

# Remote (replica) Dynamo client for conflict simulation
_REPLICA_REGION = "eu-west-1"
_dy_replica = _boto3.resource("dynamodb", region_name=_REPLICA_REGION, config=_BotoCfg(retries={"max_attempts":5,"mode":"standard"}))
_replica_table = _dy_replica.Table(_TABLE_NAME)

def _to_decimal_tree(obj):
    return _json.loads(_json.dumps(obj), parse_float=Decimal)

@app.post("/simulate-conflict")
def simulate_conflict(product_id: str, region_code: str = "us-east-1",
                      title_local: str = "LOCAL_TITLE", price_local: float = 100.0,
                      title_remote: str = "REMOTE_TITLE", price_remote: float = 101.0):
    """
    Writes the same PK/SK from two regions with different values to create a conflict.
    DynamoDB Global Tables will reconcile (effectively last-writer-wins by system timestamps).
    """
    pk = f"PRODUCT#{product_id}"
    sk = f"REGION#{region_code}"
    ts_local = datetime.now(timezone.utc).isoformat()
    local_item = {
        "PK": pk, "SK": sk,
        "title": title_local,
        "price": Decimal(str(price_local)),
        "updated_at": ts_local,
        "last_writer_region": HOME_REGION
    }
    # Write in home region
    _inv_table.put_item(Item=local_item)

    # Tiny delay to make timestamps differ a bit
    # (Not strictly required, but helps make LWW behavior visible.)
    # Then write in replica region with different values
    ts_remote = datetime.now(timezone.utc).isoformat()
    remote_item = {
        "PK": pk, "SK": sk,
        "title": title_remote,
        "price": Decimal(str(price_remote)),
        "updated_at": ts_remote,
        "last_writer_region": _REPLICA_REGION
    }
    _replica_table.put_item(Item=remote_item)

    return {"written_local": local_item, "written_remote": remote_item, "note": "Read back after ~1-2s to see winner."}

@app.get("/explain-merge/{product_id}/{region_code}")
def explain_merge(product_id: str, region_code: str):
    """
    Reads the current item and explains which region 'won' based on the stored metadata.
    (DynamoDB's internal reconciliation is last-writer-wins; here we surface the result.)
    """
    key = {"PK": f"PRODUCT#{product_id}", "SK": f"REGION#{region_code}"}
    resp = _inv_table.get_item(Key=key, ConsistentRead=False)  # eventual read to reflect replication
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    winner = item.get("last_writer_region", "unknown")
    return {
        "current": item,
        "winner_region": winner,
        "explanation": "Global Tables reconcile concurrent updates; the later update (by system timestamps) wins."
    }

from pydantic import BaseModel
from datetime import datetime, timezone
from decimal import Decimal

class SimulateConflictIn(BaseModel):
    product_id: str
    region_code: str = "us-east-1"
    title_local: str = "LOCAL_TITLE"
    price_local: float = 100.0
    title_remote: str = "REMOTE_TITLE"
    price_remote: float = 101.0

@app.post("/simulate-conflict-body")
def simulate_conflict_body(body: SimulateConflictIn):
    pk = f"PRODUCT#{body.product_id}"
    sk = f"REGION#{body.region_code}"

    local_item = {
        "PK": pk, "SK": sk,
        "title": body.title_local,
        "price": Decimal(str(body.price_local)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_writer_region": HOME_REGION
    }
    _inv_table.put_item(Item=local_item)

    remote_item = {
        "PK": pk, "SK": sk,
        "title": body.title_remote,
        "price": Decimal(str(body.price_remote)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_writer_region": _REPLICA_REGION
    }
    _replica_table.put_item(Item=remote_item)

    return {"written_local": local_item, "written_remote": remote_item, "note": "Read back after ~1-2s to see winner."}
