import json
import os
from pathlib import Path

import pandas as pd

FEATURES = [f"V{i}" for i in range(1, 29)]


def add_demo_drift(current: pd.DataFrame, strength: float = 2.0) -> pd.DataFrame:
    drifted = current.copy()
    for feature in FEATURES[:5]:
        if feature in drifted:
            drifted[feature] = drifted[feature].astype(float) + strength
    if "Amount" in drifted:
        drifted["Amount"] = drifted["Amount"] * (1 + strength / 10)
    return drifted


def calculate_drift(
    reference_path: str, current_path: str, output_path: str | None = None
) -> dict:
    reference = pd.read_csv(reference_path)
    current = pd.read_csv(current_path)
    if os.getenv("DEMO_DRIFT", "false").lower() == "true":
        current = add_demo_drift(current, float(os.getenv("DRIFT_STRENGTH", "2.0")))
    shared = [
        column for column in FEATURES if column in reference and column in current
    ]
    shared += [
        column for column in ("Amount",) if column in reference and column in current
    ]
    drift_scores = {}
    for column in shared:
        left, right = reference[column].dropna(), current[column].dropna()
        if left.empty or right.empty:
            continue
        try:
            reference_counts = pd.cut(left, bins=10).value_counts(normalize=True)
            current_counts = pd.cut(right, bins=10).value_counts(normalize=True)
            drift_scores[column] = float(
                (reference_counts - current_counts).abs().fillna(0).mean()
            )
        except (TypeError, ValueError):
            drift_scores[column] = 0.0
    concept_drift = False
    if "Class" in reference and "Class" in current:
        concept_drift = (
            abs(float(reference["Class"].mean()) - float(current["Class"].mean()))
            > 0.05
        )
    report = {
        "data_drift_detected": any(score > 0.05 for score in drift_scores.values()),
        "concept_drift_detected": concept_drift,
        "drift_scores": drift_scores,
        "current_rows": len(current),
    }
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calculate feature drift report")
    parser.add_argument("--reference", default="data/train.csv")
    parser.add_argument("--current", default="data/test.csv")
    parser.add_argument("--output", default="data/drift_report.json")
    arguments = parser.parse_args()
    print(
        json.dumps(
            calculate_drift(arguments.reference, arguments.current, arguments.output),
            indent=2,
        )
    )
