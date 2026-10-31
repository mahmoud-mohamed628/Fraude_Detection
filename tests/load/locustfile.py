import os
import random

from locust import HttpUser, LoadTestShape, constant_pacing, events, task


class FraudPredictionUser(HttpUser):
    wait_time = constant_pacing(0.1)
    host = os.getenv("LOCUST_HOST", "http://localhost:8000")

    @task
    def predict(self):
        transaction = {
            "transaction_id": f"load-{random.randint(1, 1_000_000)}",
            "Time": 1000.0,
            "Amount": random.uniform(0, 2500),
        }
        transaction.update(
            {f"V{index}": random.uniform(-3, 3) for index in range(1, 29)}
        )
        self.client.post("/predict", json=transaction, name="POST /predict")


class FiftyUserShape(LoadTestShape):
    def tick(self):
        if self.get_run_time() < 60:
            return 50, 10
        return None


@events.quitting.add_listener
def report_percentiles(environment, **_kwargs):
    stats = environment.stats.get("POST /predict", method="POST")
    if stats is None:
        return
    print("POST /predict latency percentiles (ms):")
    for percentile, value in (
        (50, stats.get_current_response_time_percentile(0.50)),
        (95, stats.get_current_response_time_percentile(0.95)),
        (99, stats.get_current_response_time_percentile(0.99)),
    ):
        print(f"p{percentile}: {value:.2f} ms")
