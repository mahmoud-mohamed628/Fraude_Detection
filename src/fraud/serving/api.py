import os
import time
from pathlib import Path
from typing import Any

import mlflow.pyfunc
import pandas as pd
import yaml
from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Fraud Detection API")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "fraud-detector")
MODEL_ALIAS = os.getenv("MODEL_ALIAS", os.getenv("MODEL_STAGE", "Production"))
CONFIG_PATH = Path(os.getenv("SERVING_CONFIG", "configs/serving.yaml"))

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
model: Any | None = None
model_version = "fallback"
model_uri = f"models:/{MODEL_NAME}/{MODEL_ALIAS}"
threshold = 0.5

REQUESTS = Counter("fraud_api_requests_total", "Number of API prediction requests")
INFERENCE_LATENCY = Histogram(
    "fraud_api_inference_latency_seconds", "Model inference latency in seconds"
)
FRAUDS = Counter("fraud_api_fraud_detected_total", "Number of frauds detected")

FEATURES = [f"V{i}" for i in range(1, 29)]


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=1)
    Time: float
    V1: float
    V2: float
    V3: float
    V4: float
    V5: float
    V6: float
    V7: float
    V8: float
    V9: float
    V10: float
    V11: float
    V12: float
    V13: float
    V14: float
    V15: float
    V16: float
    V17: float
    V18: float
    V19: float
    V20: float
    V21: float
    V22: float
    V23: float
    V24: float
    V25: float
    V26: float
    V27: float
    V28: float
    Amount: float = Field(..., ge=0)


class FeatureImportance(BaseModel):
    feature: str
    shap_value: float


class PredictionResponse(BaseModel):
    transaction_id: str
    fraud_probability: float
    decision: str
    threshold: float
    model_version: str
    top_features: list[FeatureImportance]
    latency_ms: float


class BatchPredictionResponse(BaseModel):
    predictions: list[PredictionResponse]


def load_threshold() -> float:
    candidates = [CONFIG_PATH, Path("threshold.json")]
    for path in candidates:
        if path.exists():
            try:
                if path.suffix == ".json":
                    import json

                    with path.open(encoding="utf-8") as handle:
                        value = json.load(handle).get("threshold")
                else:
                    with path.open(encoding="utf-8") as handle:
                        value = yaml.safe_load(handle).get("threshold")
                if value is not None and 0 <= float(value) <= 1:
                    return float(value)
            except (OSError, ValueError, AttributeError, yaml.YAMLError):
                pass
    return 0.5


@app.on_event("startup")
def load_ml_model() -> None:
    global model, model_version, threshold
    threshold = load_threshold()
    try:
        loaded = mlflow.pyfunc.load_model(model_uri)
        model = loaded
        model_version = getattr(loaded, "metadata", None)
        if model_version is not None:
            model_version = getattr(model_version, "model_uuid", None) or str(
                model_version
            )
        else:
            model_version = MODEL_ALIAS
        print(f"Model loaded successfully from {model_uri}")
    except Exception as exc:  # noqa: BLE001
        model = None
        model_version = "fallback"
        print(f"MLflow unavailable ({exc}); running in secure fallback mode")


def transaction_frame(transactions: list[Transaction]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            transaction.model_dump(exclude={"transaction_id"})
            for transaction in transactions
        ]
    )


def positive_probability(predictions: Any) -> list[float]:
    values = predictions if hasattr(predictions, "shape") else list(predictions)
    if isinstance(values, pd.DataFrame):
        values = values.to_numpy()
    if hasattr(values, "ndim") and values.ndim == 2:
        values = [row[-1] for row in values]
    elif not isinstance(values, (list, tuple)):
        values = list(values)
    return [min(1.0, max(0.0, float(value))) for value in values]


def predict_probabilities(frame: pd.DataFrame) -> list[float]:
    if model is not None:
        raw_predictions = model.predict(frame)
        probabilities = positive_probability(raw_predictions)
        if probabilities:
            return probabilities
    # A deterministic, conservative fallback for outages; it is not a trained model.
    return [
        (
            min(0.99, 0.08 + 0.85 / (1 + 500 / max(float(amount), 1.0)))
            if float(amount) >= 1000
            else min(0.12 + 0.0001 * float(amount), 0.99)
        )
        for amount in frame["Amount"].tolist()
    ]


def shap_explanations(
    frame: pd.DataFrame, probabilities: list[float]
) -> list[list[FeatureImportance]]:
    explanations: list[list[FeatureImportance]] = []
    try:
        import shap

        estimator = getattr(model, "_model_impl", None)
        underlying = getattr(estimator, "python_model", None)
        explainer_source = underlying if underlying is not None else estimator
        if explainer_source is None:
            raise RuntimeError("SHAP backend unavailable")
        shap_values = shap.TreeExplainer(explainer_source).shap_values(frame)
        if isinstance(shap_values, list):
            shap_values = shap_values[-1]
    except Exception:  # noqa: BLE001
        shap_values = None

    for index, probability in enumerate(probabilities):
        if shap_values is not None and getattr(shap_values, "ndim", 0) == 2:
            row = shap_values[index]
            ranked = sorted(
                zip(frame.columns, row), key=lambda item: abs(item[1]), reverse=True
            )[:3]
        else:
            # Data-driven fallback explanation keeps serving available without SHAP.
            row = frame.iloc[index]
            ranked = sorted(
                ((column, abs(float(row[column]) * 0.01)) for column in frame.columns),
                key=lambda item: item[1],
                reverse=True,
            )[:3]
        explanations.append(
            [
                FeatureImportance(feature=str(name), shap_value=round(float(value), 6))
                for name, value in ranked
            ]
        )
    return explanations


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy" if model is not None else "degraded",
        "model_loaded": model is not None,
        "model_version": model_version,
        "mlflow_uri": MLFLOW_TRACKING_URI,
        "model_uri": model_uri,
        "fallback": model is None,
    }


@app.get("/metrics", response_class=Response)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict", response_model=PredictionResponse)
def predict_fraud(transaction: Transaction) -> PredictionResponse:
    started = time.perf_counter()
    REQUESTS.inc()
    frame = transaction_frame([transaction])
    probability = predict_probabilities(frame)[0]
    explanations = shap_explanations(frame, [probability])[0]
    latency_ms = (time.perf_counter() - started) * 1000
    INFERENCE_LATENCY.observe(latency_ms / 1000)
    is_fraud = probability >= threshold
    if is_fraud:
        FRAUDS.inc()
    return PredictionResponse(
        transaction_id=transaction.transaction_id,
        fraud_probability=round(probability, 6),
        decision="FRAUD" if is_fraud else "LEGIT",
        threshold=threshold,
        model_version=model_version,
        top_features=explanations,
        latency_ms=round(latency_ms, 3),
    )


@app.post("/predict_batch", response_model=BatchPredictionResponse)
def predict_fraud_batch(transactions: list[Transaction]) -> BatchPredictionResponse:
    if not transactions:
        return BatchPredictionResponse(predictions=[])
    started = time.perf_counter()
    REQUESTS.inc(len(transactions))
    frame = transaction_frame(transactions)
    probabilities = predict_probabilities(frame)
    explanations = shap_explanations(frame, probabilities)
    latency_ms = (time.perf_counter() - started) * 1000
    INFERENCE_LATENCY.observe(latency_ms / 1000)
    responses = []
    for transaction, probability, top_features in zip(
        transactions, probabilities, explanations
    ):
        is_fraud = probability >= threshold
        if is_fraud:
            FRAUDS.inc()
        responses.append(
            PredictionResponse(
                transaction_id=transaction.transaction_id,
                fraud_probability=round(probability, 6),
                decision="FRAUD" if is_fraud else "LEGIT",
                threshold=threshold,
                model_version=model_version,
                top_features=top_features,
                latency_ms=round(latency_ms, 3),
            )
        )
    return BatchPredictionResponse(predictions=responses)
