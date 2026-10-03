"""
Metaheuristic Optimization Suite for EDA Synthesis Parameter Tuning (src/metaheuristics.py)

Implements three industry-standard metaheuristic optimization algorithms:
1. Particle Swarm Optimization (PSO) - Swarm intelligence exploring continuous/discrete synthesis parameters
2. Genetic Algorithm (GA) - Evolutionary optimization with tournament selection, blend crossover, and mutation
3. Simulated Annealing (SA) - Trajectory-based thermodynamic cooling metaheuristic (classic EDA technique)

Explores the Yosys synthesis parameter space:
- ABC logic optimization strategy (default, fast, dff, all, simple)
- Target clock period constraint (1.0 to 50.0 ns)
- Netlist flattening (-flatten flag)
- Resource sharing (share pass)
- FSM state encoding (auto, onehot, binary, gray)

Evaluates real multi-objective fitness over Area, Power, Timing, and Quality Score.
"""

import os
import sys
import numpy as np
from typing import Optional, Tuple, Dict, Any, List

from src.synthesis import run_synthesis
from src.power_timing import estimate_power_timing_area
from src.quality_score import compute_quality_score
from src.parser_ir import parse_verilog, summarize_ast
from src.linter import lint_ast, run_verilator_lint
from src.complexity import compute_complexity

# Dimension Mapping
# Dim 0: abc_strategy (0: default, 1: fast, 2: dff, 3: all, 4: simple)
# Dim 1: target_clock_period_ns (1.0 to 50.0 ns continuous)
# Dim 2: flatten (0: False, 1: True)
# Dim 3: resource_sharing (0: False, 1: True)
# Dim 4: fsm_encoding (0: auto, 1: onehot, 2: binary, 3: gray)

ABC_STRATEGIES = ["default", "fast", "dff", "all", "simple"]
FSM_ENCODINGS = ["auto", "onehot", "binary", "gray"]

BOUNDS_LOWER = np.array([0.0, 1.0, 0.0, 0.0, 0.0])
BOUNDS_UPPER = np.array([4.0, 50.0, 1.0, 1.0, 3.0])


def position_to_params(pos: np.ndarray) -> dict:
    """Map continuous position/chromosome vector to discrete/continuous synthesis parameters."""
    abc_idx = int(np.clip(np.round(pos[0]), 0, len(ABC_STRATEGIES) - 1))
    clock_ns = round(float(np.clip(pos[1], 1.0, 50.0)), 2)
    flatten = bool(np.round(np.clip(pos[2], 0, 1)))
    sharing = bool(np.round(np.clip(pos[3], 0, 1)))
    fsm_idx = int(np.clip(np.round(pos[4]), 0, len(FSM_ENCODINGS) - 1))

    return {
        "abc_strategy": ABC_STRATEGIES[abc_idx],
        "target_clock_period_ns": clock_ns,
        "flatten": flatten,
        "resource_sharing": sharing,
        "fsm_encoding": FSM_ENCODINGS[fsm_idx]
    }


def param_hash(params: dict) -> str:
    """Generate a unique string key for candidate parameter caching."""
    return f"{params['abc_strategy']}_{params['target_clock_period_ns']}_{params['flatten']}_{params['resource_sharing']}_{params['fsm_encoding']}"


def evaluate_candidate(
    filepath: str,
    params: dict,
    baseline_metrics: dict,
    objective: str,
    cache: dict,
    ast=None,
    ir_mod=None,
    lint_w=None,
    verilator_w=None,
    comp_m=None
) -> Tuple[float, dict]:
    """
    Execute real Yosys synthesis for the given parameters and evaluate multi-objective fitness loss.
    Lower fitness is better.
    """
    key = param_hash(params)
    if key in cache:
        return cache[key]

    synth_res = run_synthesis(filepath, synth_options=params)
    pt_res = estimate_power_timing_area(synth_res, comp_m)

    if ast is not None and comp_m is not None:
        qs_res = compute_quality_score(lint_w, comp_m, synth_res, verilator_warnings=verilator_w)
    else:
        qs_res = {'total_score': 80.0}

    area = float(pt_res.get('total_area_um2', 100.0))
    power = float(pt_res.get('total_power_uw', 50.0))
    delay = float(pt_res.get('critical_path_ps', 1000.0))
    quality = float(qs_res.get('total_score', 80.0))

    base_area = max(float(baseline_metrics.get('total_area_um2', 100.0)), 1e-3)
    base_power = max(float(baseline_metrics.get('total_power_uw', 50.0)), 1e-3)
    base_delay = max(float(baseline_metrics.get('critical_path_ps', 1000.0)), 1.0)
    base_quality = max(float(baseline_metrics.get('quality_score', 80.0)), 1.0)

    norm_area = area / base_area
    norm_power = power / base_power
    norm_delay = delay / base_delay
    norm_quality = base_quality / max(quality, 1.0)

    # Multi-objective weights selection
    if objective == "area":
        w_a, w_p, w_d, w_q = 0.65, 0.15, 0.15, 0.05
    elif objective == "power":
        w_a, w_p, w_d, w_q = 0.15, 0.65, 0.15, 0.05
    elif objective == "timing":
        w_a, w_p, w_d, w_q = 0.15, 0.15, 0.65, 0.05
    else:  # balanced
        w_a, w_p, w_d, w_q = 0.35, 0.35, 0.25, 0.05

    fitness = (w_a * norm_area) + (w_p * norm_power) + (w_d * norm_delay) + (w_q * norm_quality)

    metrics = {
        "total_area_um2": round(area, 2),
        "total_power_uw": round(power, 4),
        "critical_path_ps": int(delay),
        "quality_score": round(quality, 1),
        "total_cells": getattr(synth_res, "total_cells", 0)
    }

    cache[key] = (fitness, metrics)
    return fitness, metrics


def _extract_base_context(filepath: str):
    """Extract AST, IR, lint warnings, and complexity metrics for quality evaluation."""
    try:
        ast = parse_verilog(filepath)
        ir = summarize_ast(ast, file_path=filepath)
        ir_mod = ir["modules"][0] if (ir.get("modules") and len(ir["modules"]) > 0) else {}
        lint_w = lint_ast(ast)
        verilator_w = run_verilator_lint(filepath)
        comp_m = compute_complexity(ast, ir_mod)
    except Exception:
        ast, ir_mod, lint_w, verilator_w, comp_m = None, None, None, "", None

    default_params = {
        "abc_strategy": "default",
        "target_clock_period_ns": 10.0,
        "flatten": True,
        "resource_sharing": False,
        "fsm_encoding": "auto"
    }

    base_synth = run_synthesis(filepath, synth_options=default_params)
    base_pt = estimate_power_timing_area(base_synth, comp_m)
    base_qs = compute_quality_score(lint_w, comp_m, base_synth, verilator_warnings=verilator_w) if comp_m else {'total_score': 80.0}

    baseline_metrics = {
        "total_area_um2": round(float(base_pt.get('total_area_um2', 0.0)), 2),
        "total_power_uw": round(float(base_pt.get('total_power_uw', 0.0)), 4),
        "critical_path_ps": int(base_pt.get('critical_path_ps', 0)),
        "quality_score": round(float(base_qs.get('total_score', 80.0)), 1),
        "total_cells": getattr(base_synth, "total_cells", 0)
    }

    return ast, ir_mod, lint_w, verilator_w, comp_m, baseline_metrics


def _build_result(
    algorithm: str,
    algorithm_name: str,
    best_params: dict,
    best_fitness: float,
    best_metrics: dict,
    baseline_metrics: dict,
    convergence_history: List[float],
    details: Optional[dict] = None
) -> dict:
    """Format standardized optimizer results dictionary with improvement deltas."""
    base_a = baseline_metrics["total_area_um2"]
    best_a = best_metrics["total_area_um2"]
    area_diff_pct = round(((base_a - best_a) / base_a * 100.0), 1) if base_a > 0 else 0.0

    base_p = baseline_metrics["total_power_uw"]
    best_p = best_metrics["total_power_uw"]
    power_diff_pct = round(((base_p - best_p) / base_p * 100.0), 1) if base_p > 0 else 0.0

    base_d = baseline_metrics["critical_path_ps"]
    best_d = best_metrics["critical_path_ps"]
    delay_diff_pct = round(((base_d - best_d) / base_d * 100.0), 1) if base_d > 0 else 0.0

    q_diff_pts = round(best_metrics["quality_score"] - baseline_metrics["quality_score"], 1)

    return {
        "algorithm": algorithm,
        "algorithm_name": algorithm_name,
        "best_params": best_params,
        "best_fitness": round(float(best_fitness), 4),
        "best_metrics": best_metrics,
        "baseline_metrics": baseline_metrics,
        "convergence_history": convergence_history,
        "baseline_vs_optimized": {
            "area_reduction_pct": area_diff_pct,
            "power_reduction_pct": power_diff_pct,
            "delay_reduction_pct": delay_diff_pct,
            "quality_gain_pts": q_diff_pts
        },
        "details": details or {}
    }


# =========================================================================
# 1. PARTICLE SWARM OPTIMIZATION (PSO)
# =========================================================================

def optimize_pso(
    filepath: str,
    objective: str = "balanced",
    n_particles: int = 12,
    n_iterations: int = 15,
    seed: Optional[int] = 42
) -> dict:
    """
    Run Particle Swarm Optimization (PSO) over the synthesis parameter space.
    """
    print(f"Starting PSO Optimization on {os.path.basename(filepath)} (objective={objective}, particles={n_particles}, iterations={n_iterations})...")
    ast, ir_mod, lint_w, verilator_w, comp_m, baseline_metrics = _extract_base_context(filepath)
    cache = {}

    if seed is not None:
        np.random.seed(seed)
    dim = len(BOUNDS_LOWER)

    positions = np.zeros((n_particles, dim))
    velocities = np.zeros((n_particles, dim))

    # Initialize particle positions (particle 0 starts at baseline default)
    positions[0] = np.array([0.0, 10.0, 1.0, 0.0, 0.0])
    for i in range(1, n_particles):
        positions[i] = BOUNDS_LOWER + np.random.rand(dim) * (BOUNDS_UPPER - BOUNDS_LOWER)
        velocities[i] = (np.random.rand(dim) - 0.5) * (BOUNDS_UPPER - BOUNDS_LOWER) * 0.1

    pbest_positions = np.copy(positions)
    pbest_fitness = np.full(n_particles, np.inf)
    pbest_metrics = [None] * n_particles

    gbest_position = None
    gbest_fitness = np.inf
    gbest_metrics = None

    # Evaluate initial swarm
    for i in range(n_particles):
        params = position_to_params(positions[i])
        fit, met = evaluate_candidate(filepath, params, baseline_metrics, objective, cache, ast, ir_mod, lint_w, verilator_w, comp_m)
        pbest_fitness[i] = fit
        pbest_metrics[i] = met

        if fit < gbest_fitness:
            gbest_fitness = fit
            gbest_position = np.copy(positions[i])
            gbest_metrics = met

    convergence_history = [round(float(gbest_fitness), 4)]

    # PSO Hyperparameters
    w = 0.729
    c1 = 1.494
    c2 = 1.494

    # Main PSO Loop
    for it in range(n_iterations):
        for i in range(n_particles):
            r1 = np.random.rand(dim)
            r2 = np.random.rand(dim)

            # Update velocity
            velocities[i] = (w * velocities[i] +
                            c1 * r1 * (pbest_positions[i] - positions[i]) +
                            c2 * r2 * (gbest_position - positions[i]))

            # Clamp velocity
            v_max = (BOUNDS_UPPER - BOUNDS_LOWER) * 0.2
            velocities[i] = np.clip(velocities[i], -v_max, v_max)

            # Update position
            positions[i] = np.clip(positions[i] + velocities[i], BOUNDS_LOWER, BOUNDS_UPPER)

            params = position_to_params(positions[i])
            fit, met = evaluate_candidate(filepath, params, baseline_metrics, objective, cache, ast, ir_mod, lint_w, verilator_w, comp_m)

            if fit < pbest_fitness[i]:
                pbest_fitness[i] = fit
                pbest_positions[i] = np.copy(positions[i])
                pbest_metrics[i] = met

            if fit < gbest_fitness:
                gbest_fitness = fit
                gbest_position = np.copy(positions[i])
                gbest_metrics = met

        convergence_history.append(round(float(gbest_fitness), 4))

    best_params = position_to_params(gbest_position)
    return _build_result(
        algorithm="pso",
        algorithm_name="Particle Swarm Optimization (PSO)",
        best_params=best_params,
        best_fitness=gbest_fitness,
        best_metrics=gbest_metrics,
        baseline_metrics=baseline_metrics,
        convergence_history=convergence_history,
        details={"particles": n_particles, "iterations": n_iterations, "evaluations": len(cache)}
    )


# =========================================================================
# 2. GENETIC ALGORITHM (GA)
# =========================================================================

def optimize_ga(
    filepath: str,
    objective: str = "balanced",
    population_size: int = 10,
    n_generations: int = 10,
    crossover_prob: float = 0.8,
    mutation_prob: float = 0.25,
    tournament_size: int = 3,
    seed: Optional[int] = 42
) -> dict:
    """
    Run Genetic Algorithm (GA) metaheuristic optimizer over the synthesis parameter space.
    Features:
    - Real-parameter chromosome encoding
    - Tournament selection
    - Blend / uniform crossover
    - Bounded Gaussian mutation
    - Elitism preserving top individuals across generations
    """
    print(f"Starting Genetic Algorithm Optimization on {os.path.basename(filepath)} (objective={objective}, pop={population_size}, gen={n_generations})...")
    ast, ir_mod, lint_w, verilator_w, comp_m, baseline_metrics = _extract_base_context(filepath)
    cache = {}

    if seed is not None:
        np.random.seed(seed)
    dim = len(BOUNDS_LOWER)

    # Initialize population (Individual 0 starts at baseline default)
    population = np.zeros((population_size, dim))
    population[0] = np.array([0.0, 10.0, 1.0, 0.0, 0.0])
    for i in range(1, population_size):
        population[i] = BOUNDS_LOWER + np.random.rand(dim) * (BOUNDS_UPPER - BOUNDS_LOWER)

    fitness_scores = np.full(population_size, np.inf)
    individual_metrics = [None] * population_size

    # Initial evaluation
    best_idx = 0
    for i in range(population_size):
        params = position_to_params(population[i])
        fit, met = evaluate_candidate(filepath, params, baseline_metrics, objective, cache, ast, ir_mod, lint_w, verilator_w, comp_m)
        fitness_scores[i] = fit
        individual_metrics[i] = met
        if fit < fitness_scores[best_idx]:
            best_idx = i

    best_chromosome = np.copy(population[best_idx])
    best_fitness = fitness_scores[best_idx]
    best_metrics = individual_metrics[best_idx]
    convergence_history = [round(float(best_fitness), 4)]

    def tournament_select() -> np.ndarray:
        t_indices = np.random.choice(population_size, size=min(tournament_size, population_size), replace=False)
        best_t_idx = t_indices[np.argmin(fitness_scores[t_indices])]
        return np.copy(population[best_t_idx])

    # Evolutionary loop
    for gen in range(n_generations):
        next_population = []
        # Elitism: retain the best individual directly
        next_population.append(np.copy(best_chromosome))

        while len(next_population) < population_size:
            # Selection
            parent1 = tournament_select()
            parent2 = tournament_select()

            # Crossover (Arithmetic Blend Crossover)
            if np.random.rand() < crossover_prob:
                alpha = np.random.uniform(-0.1, 1.1, size=dim)
                child1 = alpha * parent1 + (1.0 - alpha) * parent2
                child2 = (1.0 - alpha) * parent1 + alpha * parent2
            else:
                child1 = np.copy(parent1)
                child2 = np.copy(parent2)

            # Mutation
            for child in (child1, child2):
                if len(next_population) >= population_size:
                    break
                for d in range(dim):
                    if np.random.rand() < mutation_prob:
                        # Adaptive mutation step based on dimension range
                        span = BOUNDS_UPPER[d] - BOUNDS_LOWER[d]
                        noise = np.random.normal(0, 0.2 * span)
                        child[d] += noise

                # Boundary clipping
                child = np.clip(child, BOUNDS_LOWER, BOUNDS_UPPER)
                next_population.append(child)

        population = np.array(next_population)

        # Evaluate generation
        for i in range(population_size):
            params = position_to_params(population[i])
            fit, met = evaluate_candidate(filepath, params, baseline_metrics, objective, cache, ast, ir_mod, lint_w, verilator_w, comp_m)
            fitness_scores[i] = fit
            individual_metrics[i] = met

            if fit < best_fitness:
                best_fitness = fit
                best_chromosome = np.copy(population[i])
                best_metrics = met

        convergence_history.append(round(float(best_fitness), 4))

    best_params = position_to_params(best_chromosome)
    return _build_result(
        algorithm="ga",
        algorithm_name="Genetic Algorithm (GA)",
        best_params=best_params,
        best_fitness=best_fitness,
        best_metrics=best_metrics,
        baseline_metrics=baseline_metrics,
        convergence_history=convergence_history,
        details={
            "population_size": population_size,
            "generations": n_generations,
            "crossover_prob": crossover_prob,
            "mutation_prob": mutation_prob,
            "evaluations": len(cache)
        }
    )


# =========================================================================
# 3. SIMULATED ANNEALING (SA)
# =========================================================================

def optimize_sa(
    filepath: str,
    objective: str = "balanced",
    initial_temp: float = 1.0,
    cooling_rate: float = 0.85,
    n_iterations: int = 20,
    seed: Optional[int] = 42
) -> dict:
    """
    Run Simulated Annealing (SA) metaheuristic optimizer over the synthesis parameter space.
    Features:
    - Thermodynamic cooling schedule (geometric decay: T = T * cooling_rate)
    - Metropolis acceptance criterion (P = exp(-delta / T))
    - Stochastic neighborhood perturbation
    """
    print(f"Starting Simulated Annealing Optimization on {os.path.basename(filepath)} (objective={objective}, init_temp={initial_temp}, iters={n_iterations})...")
    ast, ir_mod, lint_w, verilator_w, comp_m, baseline_metrics = _extract_base_context(filepath)
    cache = {}

    if seed is not None:
        np.random.seed(seed)
    dim = len(BOUNDS_LOWER)

    # Initial state starts at baseline default
    current_state = np.array([0.0, 10.0, 1.0, 0.0, 0.0])
    current_params = position_to_params(current_state)
    current_fitness, current_metrics = evaluate_candidate(filepath, current_params, baseline_metrics, objective, cache, ast, ir_mod, lint_w, verilator_w, comp_m)

    best_state = np.copy(current_state)
    best_fitness = current_fitness
    best_metrics = current_metrics
    convergence_history = [round(float(best_fitness), 4)]

    temp = initial_temp
    accepted_moves = 0

    for it in range(n_iterations):
        # Generate neighbor by perturbing 1-2 random dimensions
        neighbor = np.copy(current_state)
        n_mutations = np.random.choice([1, 2])
        dims_to_mutate = np.random.choice(dim, size=n_mutations, replace=False)

        for d in dims_to_mutate:
            span = BOUNDS_UPPER[d] - BOUNDS_LOWER[d]
            # Scale mutation step by temperature (explorative when hot, exploitative when cool)
            step = np.random.normal(0, max(0.1, temp) * 0.3 * span)
            neighbor[d] += step

        neighbor = np.clip(neighbor, BOUNDS_LOWER, BOUNDS_UPPER)
        cand_params = position_to_params(neighbor)
        cand_fitness, cand_metrics = evaluate_candidate(filepath, cand_params, baseline_metrics, objective, cache, ast, ir_mod, lint_w, verilator_w, comp_m)

        delta = cand_fitness - current_fitness

        # Metropolis criterion
        if delta < 0:
            # Improvement: accept unconditionally
            accept = True
        else:
            # Worsening: accept with probability exp(-delta / T)
            p_accept = np.exp(-delta / max(temp, 1e-6))
            accept = np.random.rand() < p_accept

        if accept:
            current_state = np.copy(neighbor)
            current_fitness = cand_fitness
            current_metrics = cand_metrics
            accepted_moves += 1

            if cand_fitness < best_fitness:
                best_fitness = cand_fitness
                best_state = np.copy(neighbor)
                best_metrics = cand_metrics

        # Cooling schedule
        temp = max(temp * cooling_rate, 1e-4)
        convergence_history.append(round(float(best_fitness), 4))

    best_params = position_to_params(best_state)
    acceptance_rate = round((accepted_moves / n_iterations) * 100.0, 1)

    return _build_result(
        algorithm="sa",
        algorithm_name="Simulated Annealing (SA)",
        best_params=best_params,
        best_fitness=best_fitness,
        best_metrics=best_metrics,
        baseline_metrics=baseline_metrics,
        convergence_history=convergence_history,
        details={
            "initial_temp": initial_temp,
            "final_temp": round(float(temp), 5),
            "cooling_rate": cooling_rate,
            "iterations": n_iterations,
            "acceptance_rate_pct": acceptance_rate,
            "evaluations": len(cache)
        }
    )


# =========================================================================
# 4. UNIFIED DISPATCHER
# =========================================================================

def optimize(
    filepath: str,
    algorithm: str = "pso",
    objective: str = "balanced",
    **kwargs
) -> dict:
    """
    Unified entry point for metaheuristic synthesis optimization.
    Supported algorithms:
    - 'pso': Particle Swarm Optimization
    - 'ga': Genetic Algorithm
    - 'sa': Simulated Annealing
    """
    algo = str(algorithm).strip().lower()

    if algo in ("ga", "genetic", "genetic_algorithm"):
        pop = kwargs.get("population_size") or kwargs.get("n_particles", 10)
        gens = kwargs.get("n_generations") or kwargs.get("n_iterations", 10)
        return optimize_ga(
            filepath=filepath,
            objective=objective,
            population_size=pop,
            n_generations=gens,
            crossover_prob=kwargs.get("crossover_prob", 0.8),
            mutation_prob=kwargs.get("mutation_prob", 0.25),
            seed=kwargs.get("seed", 42)
        )
    elif algo in ("sa", "annealing", "simulated_annealing"):
        iters = kwargs.get("n_iterations", 20)
        return optimize_sa(
            filepath=filepath,
            objective=objective,
            initial_temp=kwargs.get("initial_temp", 1.0),
            cooling_rate=kwargs.get("cooling_rate", 0.85),
            n_iterations=iters,
            seed=kwargs.get("seed", 42)
        )
    else:
        # Default: PSO
        parts = kwargs.get("n_particles", 12)
        iters = kwargs.get("n_iterations", 15)
        return optimize_pso(
            filepath=filepath,
            objective=objective,
            n_particles=parts,
            n_iterations=iters,
            seed=kwargs.get("seed", 42)
        )
