"""
Train a GradientBoostingRegressor on the generated synthesis dataset.
Predicts area_um2, power_uw, delay_ps from gate-level features.

Usage:
  python train_power_model.py

Saves the trained model to models/power_timing_model.pkl
"""

import os
import sys
import json

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import joblib

DATASET = os.path.join(os.path.dirname(__file__), "data_generation", "synthesis_dataset.csv")
MODEL_OUT = os.path.join(os.path.dirname(__file__), "models", "power_timing_model.pkl")
META_OUT  = os.path.join(os.path.dirname(__file__), "models", "model_meta.json")

FEATURE_COLS = [
    'total_cells', 'ff_cells', 'logic_cells', 'mux_cells', 'buf_cells',
    'wires', 'wire_bits', 'memory_bits', 'register_bits',
    'clock_domains', 'approx_cc', 'nesting_depth', 'port_count', 'always_blocks',
]
TARGET_COLS = ['area_um2', 'power_uw', 'delay_ps']


def main():
    if not os.path.exists(DATASET):
        print(f"[train] Dataset not found: {DATASET}")
        print("[train] Run:  python data_generation/generate_dataset.py  first.")
        sys.exit(1)

    df = pd.read_csv(DATASET)
    print(f"[train] Loaded {len(df)} samples from {DATASET}")
    print(f"[train] Columns: {list(df.columns)}")

    X = df[FEATURE_COLS].fillna(0)
    y = df[TARGET_COLS].fillna(0)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"[train] Train: {len(X_train)}  Test: {len(X_test)}")

    base_gb = GradientBoostingRegressor(
        n_estimators=200,
        learning_rate=0.08,
        max_depth=4,
        subsample=0.8,
        random_state=42,
    )

    model = Pipeline([
        ('scaler', StandardScaler()),
        ('regressor', MultiOutputRegressor(base_gb, n_jobs=-1)),
    ])

    print("[train] Fitting model…")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_pred_df = pd.DataFrame(y_pred, columns=TARGET_COLS)
    y_test_reset = y_test.reset_index(drop=True)

    metrics = {}
    print("\n[train] Evaluation on held-out test set:")
    print(f"  {'Target':<15} {'MAE':>12} {'RMSE':>12}")
    print(f"  {'-'*40}")
    for col in TARGET_COLS:
        mae  = mean_absolute_error(y_test_reset[col], y_pred_df[col])
        rmse = root_mean_squared_error(y_test_reset[col], y_pred_df[col])
        metrics[col] = {'mae': round(mae, 4), 'rmse': round(rmse, 4)}
        print(f"  {col:<15} {mae:>12.4f} {rmse:>12.4f}")

    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)
    joblib.dump(model, MODEL_OUT)
    print(f"\n[train] Model saved -> {MODEL_OUT}")

    meta = {
        'n_train': len(X_train),
        'n_test': len(X_test),
        'features': FEATURE_COLS,
        'targets': TARGET_COLS,
        'metrics': metrics,
    }
    with open(META_OUT, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"[train] Metadata saved -> {META_OUT}")


if __name__ == '__main__':
    main()
