import json
import random
import time

from kafka import KafkaProducer


def generate_transaction():
    tx = {
        "transaction_id": f"tx_{random.randint(100000, 999999)}",
        "Time": round(time.time() % 100000, 2),
        "Amount": round(random.uniform(5.0, 1000.0), 2),
    }
    # Générer les features PCA (V1 à V28)
    for i in range(1, 29):
        tx[f"V{i}"] = round(random.uniform(-3.0, 3.0), 4)

    return tx


def start_producer():
    producer = KafkaProducer(
        bootstrap_servers=["localhost:9092"],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    print("🚀 Streaming producer started... Press Ctrl+C to stop.")
    try:
        while True:
            tx = generate_transaction()
            producer.send("bank-transactions", value=tx)
            print(f"Sent transaction: {tx['transaction_id']} | Amount=${tx['Amount']}")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n🛑 Producer stopped.")


if __name__ == "__main__":
    start_producer()
