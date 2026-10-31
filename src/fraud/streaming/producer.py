import json
import os
import random
import time
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer

FEATURES = [f"V{i}" for i in range(1, 29)]
BROKER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DATA_PATH = Path(os.getenv("TEST_DATA_PATH", "data/test.csv"))


def load_transactions() -> list[dict]:
    if DATA_PATH.exists():
        frame = pd.read_csv(DATA_PATH)
        rows = frame.to_dict("records")
        return [
            {
                key: value.item() if hasattr(value, "item") else value
                for key, value in row.items()
            }
            for row in rows
        ]
    return []


def generate_transaction(index: int, fraud: bool = False) -> dict:
    tx = {
        "transaction_id": f"tx-{int(time.time() * 1000)}-{index}",
        "Time": round(time.time() % 100000, 2),
        "Amount": round(
            random.uniform(1000, 5000) if fraud else random.uniform(5, 250), 2
        ),
    }
    for feature in FEATURES:
        offset = random.uniform(4, 8) if fraud else 0
        tx[feature] = round(random.uniform(-3, 3) + offset, 4)
    if fraud:
        tx["_simulated_fraud"] = True
    return tx


def start_producer() -> None:
    producer = KafkaProducer(
        bootstrap_servers=BROKER.split(";"),
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        retries=5,
    )
    speed = max(float(os.getenv("PRODUCER_SPEED", "1")), 0.01)
    fraud_ratio = min(max(float(os.getenv("FRAUD_INJECTION_RATE", "0.05")), 0), 1)
    burst_every = int(os.getenv("FRAUD_BURST_EVERY", "100"))
    source = load_transactions()
    print(f"Streaming producer started at {speed} messages/second")
    index = 0
    while True:
        if source:
            tx = dict(source[index % len(source)])
            tx.setdefault("transaction_id", f"tx-{index}")
        else:
            tx = generate_transaction(index)
        burst = burst_every > 0 and index > 0 and index % burst_every == 0
        if (random.random() < fraud_ratio or burst) and source:
            tx["Amount"] = round(
                max(float(tx.get("Amount", 0)), random.uniform(1000, 5000)), 2
            )
            tx["_simulated_fraud"] = True
        producer.send("transactions", value=tx)
        index += 1
        time.sleep(1 / speed)


if __name__ == "__main__":
    start_producer()
