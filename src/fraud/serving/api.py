import os

import mlflow.pyfunc
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Fraud Detection API")

# MLflow Tracking Server URI (Conteneur MLflow f docker-compose)
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "fraud_detection_model")
MODEL_STAGE = os.getenv("MODEL_STAGE", "Production")

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
model = None


@app.on_event("startup")
def load_ml_model():
    global model
    try:
        model_uri = f"models:/{MODEL_NAME}/{MODEL_STAGE}"
        model = mlflow.pyfunc.load_model(model_uri)
        print(f"✅ MLflow Model loaded successfully from {model_uri}")
    except Exception as e:  # noqa: BLE001
        print(
            f"⚠️ Could not load model from MLflow ({e}). Running in fallback/mock mode."
        )


class Transaction(BaseModel):
    transaction_id: str
    Time: float
    V1: float
    V2: float
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


@app.post("/predict", response_model=PredictionResponse)
def predict_fraud(transaction: Transaction):
    # Transformer la transaction en DataFrame pour le modèle ML
    input_data = pd.DataFrame([transaction.dict(exclude={"transaction_id"})])

    if model is not None:
        # Prediction avec le vrai modèle MLflow
        probs = model.predict(input_data)
        fraud_prob = float(probs[0])
        model_ver = "mlflow_registered"
    else:
        # Fallback Mock
        fraud_prob = 0.91 if transaction.Amount > 1000 else 0.12
        model_ver = "1_mock"

    is_fraud = fraud_prob >= 0.5

    return PredictionResponse(
        transaction_id=transaction.transaction_id,
        fraud_probability=round(fraud_prob, 4),
        decision="FRAUD" if is_fraud else "LEGIT",
        threshold=0.5,
        model_version=model_ver,
        top_features=[
            FeatureImportance(feature="Amount", shap_value=0.8),
            FeatureImportance(feature="V1", shap_value=0.5),
        ],
        latency_ms=1.5,
    )


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "mlflow_uri": MLFLOW_TRACKING_URI,
    }
