# Global Catalog (Multi-Region)

A globally distributed product catalog with regional data locality, cross-region discovery, and automated failover.  
Built for a master's Database Design class with a focus on schema design, keys, replication, conflict resolution, and measurable SLOs (latency, availability).

## Goals
- Regional reads/writes with low latency
- Cross-region search with controlled consistency
- Inventory sync with deterministic merges
- Automated failover and audit history

## Stack
- **DB:** DynamoDB Global Tables (primary), optional CockroachDB for comparison
- **IaC:** Terraform
- **Runtime:** Python (boto3 / FastAPI)
- **Load Testing:** k6
- **CI/CD:** GitHub Actions (to be added)

## Structure
- `infra/terraform/` – global tables, IAM, parameters
- `src/lib/` – catalog client (routing, retries, conflict handling)
- `src/app/` – FastAPI service for CRUD/search/failover demo
- `tests/` – unit/integration tests
- `docs/` – diagrams, design notes, benchmarks
- `scripts/` – helper scripts
