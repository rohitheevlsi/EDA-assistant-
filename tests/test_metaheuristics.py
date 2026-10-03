"""
Unit tests for Metaheuristic Optimization Suite (PSO, Genetic Algorithm, Simulated Annealing).
"""

import os
import pytest
from src.metaheuristics import (
    optimize_pso,
    optimize_ga,
    optimize_sa,
    optimize
)
from eda_assistant import analyze


TEST_VERILOG = "tests/verilog/clean_fsm.v"


def test_genetic_algorithm_standalone():
    assert os.path.exists(TEST_VERILOG)
    res = optimize_ga(
        TEST_VERILOG,
        objective="balanced",
        population_size=4,
        n_generations=2,
        seed=42
    )

    assert res["algorithm"] == "ga"
    assert "Genetic Algorithm" in res["algorithm_name"]
    assert "best_params" in res
    assert "abc_strategy" in res["best_params"]
    assert "target_clock_period_ns" in res["best_params"]
    assert "best_metrics" in res
    assert "baseline_metrics" in res
    assert "convergence_history" in res
    assert len(res["convergence_history"]) == 3  # Initial + 2 generations
    assert "baseline_vs_optimized" in res
    assert "details" in res
    assert res["details"]["population_size"] == 4


def test_simulated_annealing_standalone():
    assert os.path.exists(TEST_VERILOG)
    res = optimize_sa(
        TEST_VERILOG,
        objective="power",
        initial_temp=1.0,
        cooling_rate=0.8,
        n_iterations=3,
        seed=42
    )

    assert res["algorithm"] == "sa"
    assert "Simulated Annealing" in res["algorithm_name"]
    assert "best_params" in res
    assert "best_metrics" in res
    assert "convergence_history" in res
    assert len(res["convergence_history"]) == 4  # Initial + 3 iterations
    assert "details" in res
    assert "acceptance_rate_pct" in res["details"]


def test_unified_dispatcher():
    assert os.path.exists(TEST_VERILOG)
    # Test GA dispatch
    res_ga = optimize(TEST_VERILOG, algorithm="ga", objective="area", population_size=3, n_generations=2)
    assert res_ga["algorithm"] == "ga"

    # Test SA dispatch
    res_sa = optimize(TEST_VERILOG, algorithm="sa", objective="timing", n_iterations=2)
    assert res_sa["algorithm"] == "sa"

    # Test PSO dispatch
    res_pso = optimize(TEST_VERILOG, algorithm="pso", objective="balanced", n_particles=3, n_iterations=2)
    assert res_pso["algorithm"] == "pso"


def test_full_pipeline_with_ga():
    assert os.path.exists(TEST_VERILOG)
    report = analyze(
        TEST_VERILOG,
        use_llm=False,
        use_synth=True,
        use_tb=False,
        use_ai=False,
        use_optimize=True,
        optimizer_algo="ga",
        optimize_for="area",
        pso_particles=3,
        pso_iterations=2
    )

    assert report.pso_result is not None
    assert report.pso_result["algorithm"] == "ga"
    assert "GENETIC ALGORITHM" in report.to_text().upper()
