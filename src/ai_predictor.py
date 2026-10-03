"""
AI Prediction Engine (src/ai_predictor.py)
Uses a trained ML model (RandomForest) to predict RTL quality and classify defect risk patterns
from structural features extracted from the design IR, complexity metrics, and lint output.
"""

import os
import sys
import numpy as np
import joblib

# Relative path for model loading
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'ai_predictor.joblib')

FEATURE_KEYS = [
    'signal_count',
    'always_block_count',
    'cyclomatic_complexity',
    'register_bit_count',
    'clock_domain_count',
    'port_count',
    'if_count',
    'case_count',
    'max_nesting_depth',
    'lint_cdc_count',
    'lint_multidriven_count',
    'lint_latch_count',
    'lint_blocking_count',
    'lint_nonblocking_count',
    'lint_other_count',
    'verilator_warning_count',
    'verilator_error_count'
]


def extract_features(ir_mod=None, complexity_metrics=None, lint_warnings=None, verilator_warnings="") -> dict:
    """
    Extract a fixed-length numeric feature vector dict from design IR, complexity, and lint outputs.
    """
    ir_mod = ir_mod or {}
    cx = complexity_metrics or {}
    lint = lint_warnings or []
    verilator = verilator_warnings or ""

    if isinstance(verilator, list):
        verilator = "\n".join(verilator)

    v_warns = sum(1 for line in verilator.splitlines() if "%Warning-" in line or "%Warning:" in line)
    v_errs = sum(1 for line in verilator.splitlines() if "%Error-" in line or "%Error:" in line or "ERROR" in line)

    cdc_count = sum(1 for w in lint if '[CDC-CROSSING]' in w or 'CDC' in w)
    multi_count = sum(1 for w in lint if '[MULTI-DRIVEN]' in w or 'MULTI' in w)
    latch_count = sum(1 for w in lint if '[LATCH]' in w or 'LATCH' in w)
    blocking_count = sum(1 for w in lint if '[BLOCKING-IN-SEQ]' in w or 'BLOCKING' in w)
    nonblocking_count = sum(1 for w in lint if '[NONBLOCKING-IN-COMB]' in w or 'NONBLOCKING' in w)
    other_lint = max(0, len(lint) - (cdc_count + multi_count + latch_count + blocking_count + nonblocking_count))

    signals = ir_mod.get('signals', [])
    sig_cnt = len(signals) if isinstance(signals, list) else cx.get('signal_count', 0)

    ports = ir_mod.get('ports', [])
    port_cnt = len(ports) if isinstance(ports, list) else cx.get('port_count', 0)

    always_cnt = ir_mod.get('always_blocks', 0)
    if isinstance(always_cnt, list):
        always_cnt = len(always_cnt)

    return {
        'signal_count': float(cx.get('signal_count', sig_cnt)),
        'always_block_count': float(cx.get('always_blocks', always_cnt)),
        'cyclomatic_complexity': float(cx.get('approximated_cyclomatic_complexity', cx.get('cyclomatic_complexity', 1))),
        'register_bit_count': float(cx.get('register_bits', 0)),
        'clock_domain_count': float(cx.get('clock_domain_count', 1 if always_cnt > 0 else 0)),
        'port_count': float(cx.get('port_count', port_cnt)),
        'if_count': float(cx.get('if_statements', 0)),
        'case_count': float(cx.get('case_statements', 0)),
        'max_nesting_depth': float(cx.get('max_nesting_depth', 0)),
        'lint_cdc_count': float(cdc_count),
        'lint_multidriven_count': float(multi_count),
        'lint_latch_count': float(latch_count),
        'lint_blocking_count': float(blocking_count),
        'lint_nonblocking_count': float(nonblocking_count),
        'lint_other_count': float(other_lint),
        'verilator_warning_count': float(v_warns),
        'verilator_error_count': float(v_errs)
    }


def _load_or_train_model():
    """Load persisted model or auto-train if absent."""
    norm_path = os.path.abspath(MODEL_PATH)
    if not os.path.exists(norm_path):
        print(f"[WARNING] Model file '{norm_path}' not found. Triggering auto-training...")
        try:
            from train_model import train_ai_model
            train_ai_model()
        except Exception as e:
            print(f"[ERROR] Auto-training failed: {e}")
            return None

    if os.path.exists(norm_path):
        try:
            package = joblib.load(norm_path)
            return package
        except Exception as e:
            print(f"[ERROR] Failed to load model file: {e}")
            return None

    return None


def _derive_grade(score: float) -> str:
    from src.quality_score import _letter_grade
    return _letter_grade(score)


def predict_quality(features: dict, rule_score: dict = None) -> dict:
    """
    Predict RTL quality score, letter grade, confidence, and defect risk flags.
    Compares prediction against rule-based score if provided.
    """
    package = _load_or_train_model()

    if not package or "model" not in package:
        # Fallback heuristic prediction if model unavailable
        predicted_score = 80.0
        if rule_score and 'total_score' in rule_score:
            predicted_score = float(rule_score['total_score'])
        return {
            "predicted_score": round(predicted_score, 1),
            "predicted_grade": _derive_grade(predicted_score),
            "confidence": 0.50,
            "risk_flags": ["Model fallback active (using default estimator)"],
            "model_vs_rule_delta": 0.0
        }

    model = package["model"]
    feature_keys = package.get("feature_keys", FEATURE_KEYS)

    vec = [float(features.get(k, 0.0)) for k in feature_keys]
    X_in = np.array([vec])

    predicted_score = float(model.predict(X_in)[0])
    predicted_score = max(0.0, min(100.0, predicted_score))

    # Calculate confidence based on tree variance across estimators
    if hasattr(model, "estimators_"):
        tree_preds = [float(e.predict(X_in)[0]) for e in model.estimators_]
        std_dev = float(np.std(tree_preds))
        confidence = float(max(0.60, min(0.98, 1.0 - (std_dev / 40.0))))
    else:
        confidence = 0.85

    # Determine risk flags based on structural features & prediction
    risk_flags = []
    if features.get('lint_cdc_count', 0) > 0:
        risk_flags.append("Unsafe Clock Domain Crossing (CDC) Hazard")
    if features.get('lint_multidriven_count', 0) > 0:
        risk_flags.append("Multi-Driven Net Hazard")
    if features.get('lint_latch_count', 0) > 0:
        risk_flags.append("Unintended Latch Inference Risk")
    if features.get('cyclomatic_complexity', 0) > 20:
        risk_flags.append("High Cyclomatic Control Complexity")
    if features.get('max_nesting_depth', 0) > 4:
        risk_flags.append("Deep Control Nesting Depth")
    if features.get('verilator_error_count', 0) > 0:
        risk_flags.append("Verilator Compilation Error Risk")
    elif features.get('verilator_warning_count', 0) > 2:
        risk_flags.append("Verilator Warning Count Risk")

    if not risk_flags and predicted_score >= 85:
        risk_flags.append("Clean Synthesizable Design Structure")

    rule_val = float(rule_score.get('total_score', predicted_score)) if rule_score else predicted_score
    delta = round(rule_val - predicted_score, 1)

    if abs(delta) > 15.0:
        risk_flags.append(f"Model-Rule Disagreement ({delta:+.1f} pts delta)")

    return {
        "predicted_score": round(predicted_score, 1),
        "predicted_grade": _derive_grade(predicted_score),
        "confidence": round(confidence, 2),
        "risk_flags": risk_flags,
        "model_vs_rule_delta": delta
    }
