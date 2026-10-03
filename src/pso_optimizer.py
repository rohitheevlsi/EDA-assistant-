"""
Metaheuristic Optimizer Wrapper (src/pso_optimizer.py)
Maintains backward compatibility while exposing the full metaheuristic suite (PSO, GA, SA).
"""

from src.metaheuristics import (
    ABC_STRATEGIES,
    FSM_ENCODINGS,
    BOUNDS_LOWER,
    BOUNDS_UPPER,
    position_to_params,
    param_hash,
    evaluate_candidate,
    optimize_pso,
    optimize_ga,
    optimize_sa,
    optimize
)

__all__ = [
    "ABC_STRATEGIES",
    "FSM_ENCODINGS",
    "BOUNDS_LOWER",
    "BOUNDS_UPPER",
    "position_to_params",
    "param_hash",
    "evaluate_candidate",
    "optimize_pso",
    "optimize_ga",
    "optimize_sa",
    "optimize"
]
