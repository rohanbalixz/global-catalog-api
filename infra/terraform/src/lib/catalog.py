import os, json, time
from typing import Dict, Any, Tuple
from decimal import Decimal
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

TABLE_NAME = os.getenv("TABLE_NAME", "GlobalCatalog")
HOME_REGION = os.getenv("HOME_REGION", "us-east-1")
READ_CONSISTENCY = os.getenv("READ_CONSISTENCY", "strong-local")  # strong-local | eventual-global

_boto_cfg = Config(retries={"max_attempts": 5, "mode": "standard"}, read_timeout=2, connect_timeout=2)
_dynamo = boto3.resource("dynamodb", region_name=HOME_REGION, config=_boto_cfg)
_table = _dynamo.Table(TABLE_NAME)

def _timed(fn, *args, **kwargs) -> Tuple[float, Any]:
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    return (time.perf_counter() - t0) * 1000.0, out  # ms

def _sanitize_for_ddb(d: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, float):
            out[k] = Decimal(str(v))
        elif isinstance(v, dict):
            out[k] = _sanitize_for_ddb(v)
        elif isinstance(v, list):
            out[k] = [Decimal(str(x)) if isinstance(x, float) else x for x in v]
        else:
            out[k] = v
    return out

def put_product_region(product_id: str, region_code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = json.loads(json.dumps(payload), parse_float=Decimal)
    payload = _sanitize_for_ddb(payload)
    item = {
        "PK": f"PRODUCT#{product_id}",
        "SK": f"REGION#{region_code}",
        "last_writer_region": HOME_REGION,
        **payload,
    }
    ms, _ = _timed(_table.put_item, Item=item)
    return {"ok": True, "latency_ms": round(ms, 2), "item": item}

def get_product_region(product_id: str, region_code: str) -> Dict[str, Any]:
    consistent = READ_CONSISTENCY == "strong-local"
    ms, resp = _timed(
        _table.get_item,
        Key={"PK": f"PRODUCT#{product_id}", "SK": f"REGION#{region_code}"},
        ConsistentRead=consistent,
    )
    item = resp.get("Item")
    return {
        "found": item is not None,
        "item": item,
        "latency_ms": round(ms, 2),
        "consistency": "strong" if consistent else "eventual",
        "region": HOME_REGION,
    }

def upsert_inventory(product_id: str, warehouse_id: str, region_code: str, inc: int = 0, dec: int = 0) -> Dict[str, Any]:
    """
    PN-counter using flat numeric attributes + ADD (avoids overlapping document paths).
    Creates attributes if missing, then atomically adds deltas.
    """
    key = {"PK": f"PRODUCT#{product_id}", "SK": f"INV#{warehouse_id}#{region_code}"}
    inc_attr = f"inc_{HOME_REGION.replace('-', '_')}"
    dec_attr = f"dec_{HOME_REGION.replace('-', '_')}"
    update_expr = "ADD #i :inc, #d :dec"
    ms, resp = _timed(
        _table.update_item,
        Key=key,
        UpdateExpression=update_expr,
        ExpressionAttributeNames={"#i": inc_attr, "#d": dec_attr},
        ExpressionAttributeValues={":inc": inc, ":dec": dec},
        ReturnValues="ALL_NEW",
    )
    return {"ok": True, "latency_ms": round(ms, 2), "item": resp.get("Attributes", {})}

def compute_merged_qty(item: Dict[str, Any]) -> int:
    """Compute merged qty by summing inc_* and dec_* attributes."""
    inc_total = sum(int(v) for k, v in item.items() if isinstance(k, str) and k.startswith("inc_"))
    dec_total = sum(int(v) for k, v in item.items() if isinstance(k, str) and k.startswith("dec_"))
    return inc_total - dec_total
