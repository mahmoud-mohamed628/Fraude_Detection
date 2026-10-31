import json
import requests
from kafka import KafkaConsumer

API_URL = "http://localhost:8000/predict"


def start_consumer():
    consumer = KafkaConsumer(
        "bank-transactions",
        bootstrap_servers=["localhost:9092"],
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        group_id="fraud-detector-group",
    )

    print("📥 Streaming consumer started... Waiting for transactions from Redpanda...")
    try:
        for message in consumer:
            tx = message.value
            print(f"\n📩 Received transaction | Amount: ${tx.get('Amount')}")

            try:
                response = requests.post(API_URL, json=tx, timeout=2)
                if response.status_code == 200:
                    print(f"   ⚡ API Prediction: {response.json()}")
                else:
                    print(f"   ⚠️ API Error ({response.status_code}): {response.text}")
            except Exception as e:
                print(f"   ❌ Could not connect to API: {e}")

            print("-" * 50)
    except KeyboardInterrupt:
        print("\n🛑 Consumer stopped.")


if __name__ == "__main__":
    start_consumer()
