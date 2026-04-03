"""
anomaly_detector.py
ML-based anomaly detection (IsolationForest) and usage forecasting (LinearRegression).
Completely decoupled from UI and data collection — pure analysis.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from database import insert_anomaly

logger = logging.getLogger(__name__)

METRICS = ["cpu", "memory", "disk"]
MIN_ROWS_FOR_DETECTION = 30   # need enough history to fit IsolationForest
MIN_ROWS_FOR_FORECAST = 10


@dataclass(frozen=True)
class AnomalyResult:
    metric: str
    is_anomaly: bool
    score: float           # raw IsolationForest decision score
    current_value: float
    mean_value: float
    std_value: float


@dataclass(frozen=True)
class ForecastResult:
    metric: str
    predicted_values: List[float]
    trend: str             # "rising" | "falling" | "stable"
    confidence_r2: float


def detect_anomalies(df: pd.DataFrame) -> List[AnomalyResult]:
    """
    Run IsolationForest on the last MIN_ROWS_FOR_DETECTION rows.
    Returns one AnomalyResult per metric with is_anomaly=True if the
    most-recent reading is flagged.
    """
    results: List[AnomalyResult] = []

    if len(df) < MIN_ROWS_FOR_DETECTION:
        logger.debug("Not enough rows for anomaly detection (%d < %d)", len(df), MIN_ROWS_FOR_DETECTION)
        return results

    window = df.tail(MIN_ROWS_FOR_DETECTION)

    for metric in METRICS:
        values = window[metric].values.reshape(-1, 1)
        current_value = float(values[-1])

        scaler = StandardScaler()
        scaled = scaler.fit_transform(values)

        clf = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
        clf.fit(scaled)

        scores = clf.decision_function(scaled)
        labels = clf.predict(scaled)

        current_score = float(scores[-1])
        is_anomaly = bool(labels[-1] == -1)

        mean_val = float(np.mean(values))
        std_val = float(np.std(values))

        if is_anomaly:
            try:
                insert_anomaly(metric, current_value, current_score)
            except Exception as exc:
                logger.warning("Could not persist anomaly: %s", exc)

        results.append(AnomalyResult(
            metric=metric,
            is_anomaly=is_anomaly,
            score=current_score,
            current_value=current_value,
            mean_value=mean_val,
            std_value=std_val,
        ))

    return results


def forecast_usage(df: pd.DataFrame, intervals: Optional[int] = None) -> List[ForecastResult]:
    """
    Fit a LinearRegression per metric and project future values.
    Returns ForecastResult with predicted_values list and trend direction.
    """
    from config import config
    n = intervals or config.monitor.prediction_intervals
    results: List[ForecastResult] = []

    if len(df) < MIN_ROWS_FOR_FORECAST:
        return results

    X = np.arange(len(df)).reshape(-1, 1)

    for metric in METRICS:
        y = df[metric].values
        model = LinearRegression()
        model.fit(X, y)

        r2 = float(model.score(X, y))
        future_X = np.arange(len(df), len(df) + n).reshape(-1, 1)
        preds = model.predict(future_X).tolist()
        preds = [max(0.0, min(100.0, v)) for v in preds]

        slope = float(model.coef_[0])
        if slope > 0.5:
            trend = "rising"
        elif slope < -0.5:
            trend = "falling"
        else:
            trend = "stable"

        results.append(ForecastResult(
            metric=metric,
            predicted_values=preds,
            trend=trend,
            confidence_r2=round(r2, 3),
        ))

    return results


def compute_health_score(
    snapshot,
    idle_apps_count: int,
    heavy_apps_count: int,
    anomaly_count: int,
) -> int:
    """
    Score from 0 to 100. Deductions for high resource usage, idle/heavy apps, anomalies.
    Weighted formula documented inline.
    """
    t = __import__("config").config.thresholds
    score = 100.0

    # Resource deductions — linear above the warning threshold
    score -= max(snapshot.cpu    - t.cpu_warning,    0) * 0.6
    score -= max(snapshot.memory - t.memory_warning, 0) * 0.5
    score -= max(snapshot.disk   - t.disk_warning,   0) * 0.4

    # App hygiene deductions
    score -= min(idle_apps_count * 0.4, 15.0)
    score -= min(heavy_apps_count * 0.8, 10.0)

    # Anomaly penalty
    score -= min(anomaly_count * 3.0, 15.0)

    return max(0, min(100, int(score)))


def build_trend_dataframe(df: pd.DataFrame, forecasts: List[ForecastResult]) -> pd.DataFrame:
    """
    Merge historical and forecast rows into a single DataFrame for charting.
    Adds a 'source' column: 'historical' | 'forecast'.
    """
    hist = df[["timestamp", "cpu", "memory", "disk"]].copy()
    hist["source"] = "historical"

    if not forecasts or df.empty:
        return hist

    last_ts = df["timestamp"].iloc[-1]
    freq = pd.Timedelta(hours=1)
    future_ts = [last_ts + freq * (i + 1) for i in range(len(forecasts[0].predicted_values))]

    forecast_data = {"timestamp": future_ts, "source": "forecast"}
    for fc in forecasts:
        forecast_data[fc.metric] = fc.predicted_values

    forecast_df = pd.DataFrame(forecast_data)
    return pd.concat([hist, forecast_df], ignore_index=True)