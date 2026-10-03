"""
Train AI Prediction Engine Model
Generates a bootstrap training set from tests/verilog/ fixtures and perturbed variants,
fits a scikit-learn model, and saves it to models/ai_predictor.joblib.
"""

import os
import sys
import random
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.parser_ir import parse_verilog, summarize_ast
from src.linter import lint_ast, run_verilator_lint
from src.complexity import compute_complexity
from src.quality_score import compute_quality_score, _letter_grade

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


def extract_features_dict(ir_mod=None, complexity_metrics=None, lint_warnings=None, verilator_warnings="") -> dict:
    """Extract a numeric feature dictionary from structural IR, complexity, and lint output."""
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


def compute_synthetic_teacher_score(feat: dict) -> float:
    """Compute teacher supervision score (0-100) based on RTL quality scoring principles."""
    score = 100.0

    # Lint penalties
    score -= feat['lint_cdc_count'] * 20.0
    score -= feat['lint_multidriven_count'] * 20.0
    score -= feat['lint_latch_count'] * 12.0
    score -= feat['lint_blocking_count'] * 8.0
    score -= feat['lint_nonblocking_count'] * 8.0
    score -= feat['lint_other_count'] * 5.0

    # Verilator penalties
    score -= feat['verilator_warning_count'] * 5.0
    score -= feat['verilator_error_count'] * 25.0

    # Complexity penalties
    cc = feat['cyclomatic_complexity']
    if cc > 25:
        score -= min(20.0, (cc - 25) * 1.5)

    depth = feat['max_nesting_depth']
    if depth > 4:
        score -= min(15.0, (depth - 4) * 3.0)

    if feat['clock_domain_count'] > 1 and feat['lint_cdc_count'] > 0:
        score -= 10.0

    return float(max(0.0, min(100.0, score)))


def train_ai_model():
    print("Generating synthetic dataset from Verilog test cases...")

    test_dir = os.path.join(PROJECT_ROOT, "tests", "verilog")
    seed_samples = []

    if os.path.exists(test_dir):
        for fname in os.listdir(test_dir):
            if fname.endswith(".v"):
                fpath = os.path.join(test_dir, fname)
                try:
                    ast = parse_verilog(fpath)
                    ir = summarize_ast(ast, file_path=fpath)
                    ir_mod = ir["modules"][0] if (ir.get("modules") and len(ir["modules"]) > 0) else {}
                    lint_w = lint_ast(ast)
                    verilator_w = run_verilator_lint(fpath)
                    comp_m = compute_complexity(ast, ir_mod)
                    qs = compute_quality_score(lint_w, comp_m, None, verilator_warnings=verilator_w)

                    feat = extract_features_dict(ir_mod, comp_m, lint_w, verilator_w)
                    score = float(qs.get('total_score', 80))
                    seed_samples.append((feat, score))
                except Exception as e:
                    print(f"Skipping seed {fname} due to parsing error: {e}")

    # Fallback seed if tests/verilog had no valid files
    if not seed_samples:
        base_feat = {k: 0.0 for k in FEATURE_KEYS}
        base_feat.update({'signal_count': 8, 'port_count': 4, 'cyclomatic_complexity': 2})
        seed_samples.append((base_feat, 90.0))

    X_list = []
    y_score_list = []

    rng = random.Random(42)

    # Generate 500 perturbed synthetic samples
    for i in range(500):
        base_feat, _ = rng.choice(seed_samples)
        perturbed = dict(base_feat)

        # Apply perturbations
        perturbed['signal_count'] = max(0.0, perturbed['signal_count'] + rng.randint(-3, 10))
        perturbed['port_count'] = max(1.0, perturbed['port_count'] + rng.randint(-2, 6))
        perturbed['always_block_count'] = max(0.0, perturbed['always_block_count'] + rng.randint(-1, 3))
        perturbed['cyclomatic_complexity'] = max(1.0, perturbed['cyclomatic_complexity'] + rng.randint(-2, 15))
        perturbed['register_bit_count'] = max(0.0, perturbed['register_bit_count'] + rng.randint(-8, 32))
        perturbed['max_nesting_depth'] = max(0.0, perturbed['max_nesting_depth'] + rng.randint(-1, 4))
        perturbed['if_count'] = max(0.0, perturbed['if_count'] + rng.randint(0, 6))
        perturbed['case_count'] = max(0.0, perturbed['case_count'] + rng.randint(0, 3))

        # Inject / remove warnings
        if rng.random() < 0.2:
            perturbed['lint_cdc_count'] = float(rng.randint(1, 3))
        if rng.random() < 0.2:
            perturbed['lint_latch_count'] = float(rng.randint(1, 2))
        if rng.random() < 0.3:
            perturbed['lint_blocking_count'] = float(rng.randint(1, 4))
        if rng.random() < 0.15:
            perturbed['verilator_warning_count'] = float(rng.randint(1, 5))
        if rng.random() < 0.05:
            perturbed['verilator_error_count'] = float(rng.randint(1, 2))

        # Compute synthetic ground truth score
        score = compute_synthetic_teacher_score(perturbed)

        vec = [perturbed[k] for k in FEATURE_KEYS]
        X_list.append(vec)
        y_score_list.append(score)

    X = np.array(X_list)
    y_score = np.array(y_score_list)

    print(f"Fitting Random Forest Regressor on {len(X)} samples...")
    model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X, y_score)

    models_dir = os.path.join(PROJECT_ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)

    target_path = os.path.join(models_dir, "ai_predictor.joblib")
    package = {
        "model": model,
        "feature_keys": FEATURE_KEYS,
        "n_samples": len(X),
    }

    joblib.dump(package, target_path)
    print(f"[SUCCESS] AI Predictor model saved to {target_path}")
    return target_path


if __name__ == "__main__":
    train_ai_model()
