# Global Catalog — Data Model & Access Patterns

## Goals (from proposal)
- p95 < 10 ms local reads/writes; p95 < 50 ms cross-region reads
- 99.99% availability with DynamoDB Global Tables
- Eventual consistency globally; read-your-writes locally
- Deterministic conflict resolution for inventory & attributes
- Region-aware routing and failover

## Core Entities (single-table design on DynamoDB)
All items live in one table `GlobalCatalog` (Global Table). `PK` = partition key, `SK` = sort key.

### 1) Product (authoritative global identity)
- **PK**: `PRODUCT#<product_id>`
- **SK**: `META#<version>` (latest marked by `is_latest = true`)
- attrs: title, brand_id, category_id, canonical_attrs, created_at, updated_at

### 2) ProductRegion (regionalized attributes)
- **PK**: `PRODUCT#<product_id>`
- **SK**: `REGION#<region_code>`  (e.g., us-east-1, eu-west-1)
- attrs: localized_title, currency, price, promo_flags, region_overrides, last_writer_region, vector_clock

### 3) Inventory (CRDT-style counters)
- **PK**: `PRODUCT#<product_id>`
- **SK**: `INV#<warehouse_id>#<region_code>`
- attrs: per-region PN-Counter (increments/decrements map), tombstones for deletes, merged_qty (materialized), last_merge_ts

### 4) ReviewSummary (read-optimized)
- **PK**: `PRODUCT#<product_id>`
- **SK**: `REVIEWSUM#v<agg_version>`
- attrs: rating_avg, rating_count, last_agg_ts, source = "Amazon Customer Reviews Metadata"

### 5) Category
- **PK**: `CATEGORY#<category_id>`
- **SK**: `META#0`
- attrs: name, parent_category_id, path

### 6) Brand
- **PK**: `BRAND#<brand_id>`
- **SK**: `META#0`
- attrs: name, url

## Global Secondary Indexes (GSIs)
### GSI1: Search by Category → Products
- **GSI1PK**: `CAT#<category_id>`
- **GSI1SK**: `TITLE#<normalized_title>#<product_id>`

### GSI2: Search by Brand → Products
- **GSI2PK**: `BRAND#<brand_id>`
- **GSI2SK**: `TITLE#<normalized_title>#<product_id>`

### GSI3: Region Price Book
- **GSI3PK**: `REGION#<region_code>`
- **GSI3SK**: `PRICE#<price>#<product_id>`

### GSI4: Low-Stock Alerts (optional)
- **GSI4PK**: `ALERT#LOWSTOCK`
- **GSI4SK**: `<merged_qty>#<product_id>#<warehouse_id>`

## Access Patterns (must-have)
1. **Get product for region (critical path)** — (`PK=PRODUCT#pid`, `SK=REGION#rc`) with a strongly consistent read locally; fallback to eventual cross-region.
2. **Cross-region product read** — prefer `REGION#home_rc`; else read `META#latest` and hydrate.
3. **Search by category (title prefix)** — Query GSI1 with `GSI1PK=CAT#cid`, `GSI1SK begins_with 'TITLE#<prefix>'`.
4. **List by brand** — Query GSI2 with `GSI2PK=BRAND#bid`.
5. **Top-N by price band in a region** — Query GSI3 with `GSI3PK=REGION#rc` and `GSI3SK between PRICE#min..PRICE#max`.
6. **Inventory update (warehouse event)** — Upsert PN-counter component, then run merge to refresh `merged_qty`.
7. **Low-stock sweep** — Query GSI4 or compute via streams.

## Conflict Resolution
- **Attributes**: last-writer-wins with vector_clock + last_writer_region (auditable).
- **Inventory**: PN-Counter CRDT per region/warehouse; deletes via tombstones.
- **Tie-breaker**: region precedence `[local > same-continent > global-default]`, then lexicographic region_code.

## Capacity & Keys
- Hot partitions: suffix sharding for extreme brands/categories (e.g., `CAT#cid#s2`), adaptive repartition suggestions from client.
- Item size target < 16KB; blobs (images) in S3 with keys on item.

## Streams & Projections
- DynamoDB Streams → Lambda: build GSI4, push to OpenSearch (optional), update review aggregates.

## Security
- IAM per service principal; region-scoped write policies; encryption at rest + TLS in transit.

## Testing & SLO Validation
- k6 scenarios:
  - Local p95 < 10 ms for (1) and (6)
  - Cross-region reads p95 < 50 ms for (2)
  - Failover drill: region isolation; client hysteresis prevents flapping
- Metrics: p50/p95/p99, error rate, merged conflicts/sec, stream lag

## Notes aligned to proposal
- DynamoDB Global Tables (primary), regional latency goals
- Public dataset: Amazon Customer Reviews Metadata for product & reviews
- Implementation: Python (boto3/FastAPI), Terraform IaC, CloudWatch/Grafana, k6 for load
