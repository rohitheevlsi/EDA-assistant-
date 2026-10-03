"""
Unit tests for AI Prediction Engine and PSO Optimizer.
"""

import os
import pytest
from src.ai_predictor import extract_features, predict_quality
from src.pso_optimizer import optimize
from eda_assistant import analyze


def test_ai_predictor_standalone():
    mock_ir = {"ports": ["clk", "rst_n", "data_in", "data_out"], "signals": ["state", "next_state"], "always_blocks": 2}
    mock_comp = {"cyclomatic_complexity": 5, "register_bits": 4, "max_nesting_depth": 2}
    mock_lint = ["WARNING: LATCH inferred on line 12"]
    
    features = extract_features(mock_ir, mock_comp, mock_lint, "")
    res = predict_quality(features)
    
    assert "predicted_score" in res
    assert "predicted_grade" in res
    assert "confidence" in res
    assert "risk_flags" in res
    assert 0 <= res["predicted_score"] <= 100


def test_pso_optimizer_standalone():
    test_verilog = "tests/verilog/clean_fsm.v"
    assert os.path.exists(test_verilog)
    
    res = optimize(test_verilog, objective="balanced", n_particles=3, n_iterations=2)
    assert "best_params" in res
    assert "best_metrics" in res
    assert "baseline_metrics" in res
    assert "convergence_history" in res
    assert len(res["convergence_history"]) == 3  # Initial + 2 iterations


def test_full_pipeline_with_ai_and_pso():
    test_verilog = "tests/verilog/clean_fsm.v"
    report = analyze(
        test_verilog,
        use_llm=False,
        use_synth=True,
        use_tb=False,
        use_ai=True,
        use_optimize=True,
        optimize_for="area",
        pso_particles=3,
        pso_iterations=2
    )
    
    assert report.ai_prediction != {}
    assert "predicted_grade" in report.ai_prediction
    assert report.pso_result is not None
    assert "best_params" in report.pso_result
