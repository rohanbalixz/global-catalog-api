# Global Catalog API

## Overview
The **Global Catalog API** is a cloud-native, globally distributed product catalog service built using **FastAPI**, **AWS DynamoDB Global Tables**, and containerized with **Docker**.  
It supports real-time inventory tracking, product detail management, conflict resolution across multiple AWS regions, and high-performance load testing.

This project was developed as a demonstration of building a **highly available, low-latency, multi-region backend service**.

---

## Features
- **Product Details API** – Retrieve product information by region.
- **Inventory API** – Increment/Decrement stock at warehouse level.
- **Multi-Region Support** – Backed by DynamoDB Global Tables for replication across AWS regions.
- **Conflict Resolution** – Simulate and explain conflict resolution logic.
- **Health Check API** – Validate service and region health.
- **Load Testing** – Tested with k6 for performance benchmarks.
- **Dockerized Deployment** – Easily deployable on local or cloud environments.

---

## Architecture Diagram
![Architecture Diagram](architecture_diagram.png)

**Key Components:**
1. **FastAPI Application** – Serves API endpoints.
2. **AWS DynamoDB Global Tables** – Multi-region, strongly consistent storage.
3. **Docker** – Containerization for portability.
4. **k6** – Load testing tool to validate performance under high concurrency.

---

## API Endpoints

### 1. Health Check
**Check API and region health.**
```bash
curl -i http://127.0.0.1:8000/health
```

### 2. Get Product Details
**Retrieve details for a specific product in a specific AWS region.**
```bash
curl -s "http://127.0.0.1:8000/products/P1001/us-east-1" | python -m json.tool
```

### 3. Update Inventory
**Increment/Decrement inventory for a warehouse and region.**
```bash
curl -s -X POST "http://127.0.0.1:8000/inventory"   -H "Content-Type: application/json"   -d '{"product_id": "P1001", "warehouse_id": "W1", "region_code": "us-east-1", "inc": 10, "dec": 0}'   | python -m json.tool
```

### 4. Get Inventory by Product/Warehouse
```bash
curl -s "http://127.0.0.1:8000/inventory/P1001/W1" | python -m json.tool
```

### 5. Simulate Conflict
**Simulates concurrent updates to the same product from different regions.**
```bash
curl -s -X POST "http://127.0.0.1:8000/simulate-conflict-body"   -H "Content-Type: application/json"   -d '{"product_id":"P1001","region_code":"us-east-1","title_local":"LOCAL Aurora","price_local":129.50,"title_remote":"REMOTE Aurora","price_remote":139.00}'   | python -m json.tool
```

### 6. Explain Merge
**View the winner and explanation after a conflict resolution.**
```bash
curl -s "http://127.0.0.1:8000/explain-merge/P1001/us-east-1" | python -m json.tool
```

---

## Load Testing with k6
We used **k6** to simulate concurrent requests.

### Example Run
```bash
k6 run -e BASE_URL=http://127.0.0.1:8000 infra/terraform/k6_load.js
```

**Sample Results:**
```
http_req_duration{scenario:health_read}.......: p(95)=3.14ms
http_req_duration{scenario:product_read_write}: p(95)=50.31ms
http_req_failed................................: 0.00%
checks_succeeded...............................: 100%
```

---

## Local Setup

### 1. Clone Repository
```bash
git clone https://github.com/rohanbalixz/global-catalog-api.git
cd global-catalog-api
```

### 2. Create Virtual Environment & Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Locally
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Docker Build & Run
```bash
docker build -t global-catalog-api .
docker run -p 8000:8000 global-catalog-api
```

---

## Technologies Used
- **Python 3.10+**
- **FastAPI**
- **AWS DynamoDB Global Tables**
- **Docker**
- **k6**
- **JSON Tooling**

---

## Future Improvements
- Add authentication & role-based access control.
- Integrate CI/CD for automated deployment.
- Implement advanced conflict resolution strategies beyond last-write-wins.
- Deploy in AWS ECS or Kubernetes with autoscaling.

---

## Author
**Rohan Bali**  
Master's in Data Science – University of Massachusetts Dartmouth  
GitHub: [rohanbalixz](https://github.com/rohanbalixz)
