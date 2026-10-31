# Real-time Fraud Detection Platform

An end-to-end MLOps demonstration combining transaction streaming, model serving, persistence, drift monitoring, and operations dashboards.

## Architecture

```text
                          ┌──────────────────┐
CSV / synthetic data ───►│     Producer     │
                          └────────┬─────────┘
                                   │ transactions
                                   ▼
                          ┌──────────────────┐
                          │ Redpanda/Kafka   │◄──── transactions.dlq
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐      MLflow
                          │     Consumer     │──────────────► Model registry
                          └───┬──────────┬───┘
                              │          │
                              │ HTTP     │ prediction rows
                              ▼          ▼
                          ┌────────┐ ┌────────────┐
                          │ API    │ │ SQLite DB │◄── Streamlit
                          └────────┘ └────────────┘
```

Redpanda supplies the `transactions` and `transactions.dlq` topics. The API loads `models:/fraud-detector/Production` and falls back safely when MLflow is unavailable. The consumer retries API calls, persists predictions idempotently, and commits Kafka offsets only after processing or DLQ routing.

## Quick start

```bash
make setup
make up
```

The Compose stack exposes:

| Service | Address |
|---|---|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Redpanda | localhost:9092 |
| Streamlit | http://localhost:8501 |

## API contracts

### `GET /health`

Returns service status, loaded-model state, model version, model URI and MLflow URI.

### `GET /metrics`

Returns Prometheus request, inference-latency and detected-fraud metrics.

### `POST /predict`

```json
{
  "transaction_id": "demo-001",
  "Time": 100.0,
  "V1": 0.1,
  "V2": -0.2,
  "...": 0.0,
  "V28": 0.1,
  "Amount": 42.50
}
```

The response contains probability, decision, configured threshold, model version, latency and the top three dynamic explanations.

### `POST /predict_batch`

Receives an array of the same transaction object and returns `{"predictions": [...]}`.

Invalid negative amounts, missing `V1`–`V28`, and null values produce HTTP 422.

## Streaming controls

Configure the producer with environment variables:

```yaml
PRODUCER_SPEED: "5"             # transactions per second
FRAUD_INJECTION_RATE: "0.05"    # random anomaly proportion
FRAUD_BURST_EVERY: "100"        # anomaly burst interval
```

The producer replay order is `data/test.csv` when available; otherwise it produces deterministic Pydantic-compatible synthetic transactions. All messages use topic `transactions`. Invalid messages and exhausted API operations are sent to `transactions.dlq`.

## Drift demonstration

Generate a drift report against the training reference:

```bash
DEMO_DRIFT=true DRIFT_STRENGTH=2.0 python -m src.fraud.monitoring.drift \
  --reference data/train.csv --current data/test.csv --output data/drift_report.json
```

A second training baseline can be enabled in the dashboard and the Producer distribution can be changed with `FRAUD_INJECTION_RATE` or `DEMO_DRIFT`. The dashboard's Monitoring tab renders drift scores automatically.

## Demo walkthrough

1. Start services with `make up`.
2. Wait for the API and Streamlit health indicators.
3. Open http://localhost:8501.
4. Observe transactions and fraud ratio increasing in the Live stream tab.
5. Open http://localhost:8000/docs and submit a known suspicious amount.
6. Inspect latency/request/fraud metrics at http://localhost:8000/metrics.
7. Read processing records from SQLite:

   ```bash
   sqlite3 data/fraud.db 'select * from predictions order by timestamp desc limit 20;'
   ```

8. Set `DEMO_DRIFT=true`, rerun drift analysis, and inspect the Monitoring tab.

## Commands and quality

```bash
make lint
make test
make up
docker compose config
dvc status
```

For load testing, run Locust with 50 concurrent users:

```bash
locust -f tests/load/locustfile.py --headless -u 50 -r 10 -t 60s
```
