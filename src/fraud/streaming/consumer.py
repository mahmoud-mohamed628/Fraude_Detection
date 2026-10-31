import json
import os
import time
from datetime import UTC, datetime

import requests
from kafka import KafkaConsumer, KafkaProducer

from src.fraud.storage.db import save_prediction

BROKER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
API_URL = os.getenv("FRAUD_API_URL", "http://localhost:8000/predict")
DATABASE = os.getenv("FRAUD_DB", "data/fraud.db")


def post_with_retry(transaction: dict) -> requests.Response:
    delay = float(os.getenv("API_RETRY_INITIAL_SECONDS", "0.25"))
    for attempt in range(int(os.getenv("API_RETRY_ATTEMPTS", "5"))):
        try:
            response = requests.post(API_URL, json=transaction, timeout=5)
            if response.status_code < 500:
                return response
        except requests.RequestException:
            pass
        time.sleep(delay * (2**attempt))
    raise requests.RequestException("Fraud API remained unavailable")


def start_consumer() -> None:
    consumer = KafkaConsumer(
        "transactions",
        bootstrap_servers=BROKER.split(";"),
        value_deserializer=lambda payload: payload,
        group_id="fraud-detector-consumer",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    dlq = KafkaProducer(
        bootstrap_servers=BROKER.split(";"),
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        retries=5,
    )
    print("Streaming consumer started")
    for message in consumer:
        try:
            raw_transaction = (
                message.value.decode("utf-8")
                if isinstance(message.value, bytes)
                else message.value
            )
            transaction = json.loads(raw_transaction)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            dlq.send(
                "transactions.dlq", value={"reason": "invalid_json", "error": str(exc)}
            )
            consumer.commit()
            continue
        if not isinstance(transaction, dict) or not transaction.get("transaction_id"):
            dlq.send(
                "transactions.dlq",
                value={"reason": "invalid_transaction", "raw": transaction},
            )
            consumer.commit()
            continue
        try:
            response = post_with_retry(transaction)
            response.raise_for_status()
            prediction = response.json()
            inserted = save_prediction(
                str(transaction["transaction_id"]),
                float(prediction["fraud_probability"]),
                str(prediction["decision"]),
                float(prediction["latency_ms"]),
                datetime.now(UTC).isoformat(),
                DATABASE,
            )
            if inserted:
                print(f"Saved prediction for {transaction['transaction_id']}")
        except (requests.RequestException, ValueError, KeyError) as exc:
            dlq.send(
                "transactions.dlq",
                value={"transaction": transaction, "reason": str(exc)},
            )
        consumer.commit()


if __name__ == "__main__":
    start_consumer()
