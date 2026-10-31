import os
import sqlite3
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

DATABASE = os.getenv("FRAUD_DB", "data/fraud.db")
API_URL = os.getenv("FRAUD_API_URL", "http://localhost:8000")
DRIFT_REPORT = Path(os.getenv("DRIFT_REPORT", "data/drift_report.json"))

st.set_page_config(page_title="Fraud Real-time Monitor", layout="wide")
st.title("Fraud Detection — Live Operations")


def load_predictions():
    if not Path(DATABASE).exists():
        return pd.DataFrame(
            columns=[
                "transaction_id",
                "probability",
                "decision",
                "latency_ms",
                "timestamp",
            ]
        )
    with sqlite3.connect(DATABASE, timeout=30) as connection:
        return pd.read_sql_query(
            (
                "SELECT transaction_id, probability, decision, latency_ms, timestamp "
                "FROM predictions ORDER BY timestamp DESC LIMIT 2000"
            ),
            connection,
        )


placeholder = st.empty()
while True:
    data = load_predictions()
    with placeholder.container():
        total = len(data)
        frauds = int((data["decision"] == "FRAUD").sum()) if total else 0
        columns = st.columns(4)
        columns[0].metric("Transactions", total)
        columns[1].metric("Frauds", frauds)
        columns[2].metric("Fraud ratio", f"{frauds / total:.1%}" if total else "0.0%")
        if total:
            columns[3].metric("Mean latency", f"{data['latency_ms'].mean():.2f} ms")
        else:
            columns[3].metric("Mean latency", "—")

        tabs = st.tabs(
            ["Live stream", "System metrics", "Explainability", "Monitoring"]
        )
        with tabs[0]:
            if total:
                st.line_chart(
                    data.sort_values("timestamp").set_index("timestamp")[
                        ["probability"]
                    ]
                )
                st.dataframe(data.head(100), use_container_width=True, hide_index=True)
            else:
                st.info("Waiting for streaming predictions…")
        with tabs[1]:
            try:
                response = requests.get(f"{API_URL}/metrics", timeout=2)
                response.raise_for_status()
                st.code(response.text[-4000:], language="text")
                latencies = data["latency_ms"] if total else pd.Series(dtype=float)
                if not latencies.empty:
                    st.metric("p95 latency", f"{latencies.quantile(0.95):.2f} ms")
                    st.metric("p99 latency", f"{latencies.quantile(0.99):.2f} ms")
            except requests.RequestException as exc:
                st.warning(f"API metrics unavailable: {exc}")
        with tabs[2]:
            suspect = data[data["decision"] == "FRAUD"] if total else pd.DataFrame()
            if suspect.empty:
                st.info(
                    "No suspect transaction yet; SHAP values are returned in `/predict` responses."  # noqa: E501
                )
            else:
                st.dataframe(
                    suspect.head(20)[["transaction_id", "probability", "latency_ms"]],
                    hide_index=True,
                )
        with tabs[3]:
            if DRIFT_REPORT.exists():
                import json

                report = json.loads(DRIFT_REPORT.read_text(encoding="utf-8"))
                st.metric(
                    "Data drift",
                    "Detected" if report["data_drift_detected"] else "No drift",
                )
                st.metric(
                    "Concept drift",
                    "Detected" if report["concept_drift_detected"] else "No drift",
                )
                st.bar_chart(
                    pd.DataFrame.from_dict(
                        report["drift_scores"], orient="index", columns=["score"]
                    )
                )
            else:
                st.info("Run drift monitoring to generate data/drift_report.json.")
    time.sleep(float(os.getenv("DASHBOARD_REFRESH_SECONDS", "3")))
