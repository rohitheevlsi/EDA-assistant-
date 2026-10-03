"""
EDA Assistant - Phase 8: Unified CLI entry point (Enhanced).
Usage: python eda_assistant.py analyze <verilog_file> [--no-llm] [--no-synth] [--no-tb]
"""

import argparse
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.toolchain import setup_toolchain_env
os.environ.update(setup_toolchain_env())

from src.parser_ir import parse_verilog, summarize_ast
from src.linter import lint_ast, run_verilator_lint
from src.llm_engine import generate_explanation
from src.synthesis import run_synthesis
from src.tb_generator import generate_tb_skeleton, llm_enhance_tb, run_iverilog_check
from src.aggregator import EDAReport
from src.complexity import compute_complexity
from src.power_timing import estimate_power_timing_area
from src.quality_score import compute_quality_score


from src.ai_predictor import extract_features, predict_quality
from src.metaheuristics import optimize


def analyze(
    filepath: str,
    use_llm: bool = True,
    use_synth: bool = True,
    use_tb: bool = True,
    use_ai: bool = True,
    use_optimize: bool = False,
    optimizer_algo: str = "pso",
    optimize_for: str = "balanced",
    pso_particles: int = 12,
    pso_iterations: int = 15
) -> EDAReport:
    """Run the full EDA analysis pipeline on a single Verilog file."""

    print(f"\n[1/10] Parsing {filepath}...")
    # Read source code first
    with open(filepath, encoding="utf-8", errors="replace") as f:
        source_code = f.read()

    ast = parse_verilog(filepath)
    ir = summarize_ast(ast, file_path=filepath)
    ir_mod = ir["modules"][0] if (ir.get("modules") and len(ir["modules"]) > 0) else {}

    # Extract real module name (fallback to regex if temp file path or missing name)
    import re
    from src.parser_ir import strip_verilog_comments
    clean_code = strip_verilog_comments(source_code)
    mod_match = re.search(r'\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)', clean_code)
    parsed_mod_name = ir_mod.get("name")
    if parsed_mod_name and not parsed_mod_name.startswith("tmp") and not parsed_mod_name.endswith(".v"):
        module_name = parsed_mod_name
    elif mod_match:
        module_name = mod_match.group(1)
        ir_mod["name"] = module_name
    else:
        module_name = "custom_module"
        ir_mod["name"] = module_name

    report = EDAReport(filepath=filepath, module_name=module_name,
                       ir_summary=ir_mod, source_code=source_code)

    print(f"[2/10] Running static lint checks (10 rules)...")
    report.lint_warnings = lint_ast(ast)
    report.verilator_warnings = run_verilator_lint(filepath)

    print(f"[3/10] Computing design complexity metrics...")
    report.complexity_metrics = compute_complexity(ast, ir_mod)

    if use_synth:
        print(f"[4/10] Running Yosys synthesis...")
        report.synthesis = run_synthesis(filepath)
    else:
        print(f"[4/10] Synthesis skipped.")

    print(f"[5/10] Estimating power / timing / area...")
    if report.synthesis:
        report.power_timing = estimate_power_timing_area(
            report.synthesis, report.complexity_metrics)
    else:
        report.power_timing = {'error': 'Synthesis skipped'}

    if use_llm:
        print(f"[6/10] Querying Gemini LLM for explanation...")
        report.llm_explanation = generate_explanation(module_name, ir_mod, report.lint_warnings)
    else:
        report.llm_explanation = "(LLM skipped)"
        print(f"[6/10] LLM skipped.")

    if use_tb:
        print(f"[7/10] Generating testbench...")
        report.testbench_skeleton = generate_tb_skeleton(ir_mod)
        if use_llm:
            report.testbench_enhanced = llm_enhance_tb(module_name, ir_mod, report.testbench_skeleton)
        else:
            report.testbench_enhanced = report.testbench_skeleton

        with open(filepath) as f:
            mod_src = f.read()
        ok, compile_out, sim_out = run_iverilog_check(report.testbench_enhanced, mod_src, module_name)
        report.testbench_compiles = ok
        report.testbench_compile_output = compile_out
        report.testbench_simulation_success = ok
        report.testbench_simulation_output = sim_out
    else:
        print(f"[7/10] Testbench generation skipped.")

    print(f"[8/10] Computing RTL quality score...")
    report.quality_score = compute_quality_score(
        report.lint_warnings,
        report.complexity_metrics,
        report.synthesis,
        report.testbench_compiles,
        report.testbench_simulation_output,
        report.verilator_warnings,
    )

    if use_ai:
        print(f"[9/10] Running AI Prediction Engine...")
        features = extract_features(
            ir_mod=ir_mod,
            complexity_metrics=report.complexity_metrics,
            lint_warnings=report.lint_warnings,
            verilator_warnings=report.verilator_warnings
        )
        report.ai_prediction = predict_quality(features, report.quality_score)
    else:
        print(f"[9/10] AI Prediction Engine skipped.")

    if use_optimize:
        algo_names = {
            "pso": "Particle Swarm Optimization (PSO)",
            "ga": "Genetic Algorithm (GA)",
            "sa": "Simulated Annealing (SA)"
        }
        display_name = algo_names.get(optimizer_algo.lower(), optimizer_algo.upper())
        print(f"[10/10] Running Metaheuristic Design Optimization ({display_name})...")
        report.pso_result = optimize(
            filepath=filepath,
            algorithm=optimizer_algo,
            objective=optimize_for,
            n_particles=pso_particles,
            n_iterations=pso_iterations,
            population_size=pso_particles,
            n_generations=pso_iterations
        )
    else:
        print(f"[10/10] Metaheuristic Optimization skipped (enable with --optimize).")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="EDA Assistant — AI-driven RTL analysis tool"
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a Verilog file")
    analyze_parser.add_argument("file", help="Path to Verilog file")
    analyze_parser.add_argument("--no-llm", action="store_true", help="Skip LLM explanation")
    analyze_parser.add_argument("--no-synth", action="store_true", help="Skip Yosys synthesis")
    analyze_parser.add_argument("--no-tb", action="store_true", help="Skip testbench generation")
    analyze_parser.add_argument("--no-ai", action="store_true", help="Skip AI prediction engine")
    analyze_parser.add_argument("--optimize", action="store_true", help="Run metaheuristic design optimization")
    analyze_parser.add_argument("--optimizer", choices=["pso", "ga", "sa"], default="pso", help="Metaheuristic algorithm: pso, ga, or sa")
    analyze_parser.add_argument("--optimize-for", choices=["area", "power", "timing", "balanced"], default="balanced", help="Optimization objective target")
    analyze_parser.add_argument("--pso-particles", "--opt-particles", dest="pso_particles", type=int, default=12, help="Number of particles / population size")
    analyze_parser.add_argument("--pso-iterations", "--opt-iterations", dest="pso_iterations", type=int, default=15, help="Number of iterations / generations")
    analyze_parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    analyze_parser.add_argument("--save", help="Save report to file")

    args = parser.parse_args()

    if args.command == "analyze":
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            sys.exit(1)

        report = analyze(
            args.file,
            use_llm=not args.no_llm,
            use_synth=not args.no_synth,
            use_tb=not args.no_tb,
            use_ai=not args.no_ai,
            use_optimize=args.optimize,
            optimizer_algo=getattr(args, "optimizer", "pso"),
            optimize_for=args.optimize_for,
            pso_particles=args.pso_particles,
            pso_iterations=args.pso_iterations,
        )

        if args.json:
            import json
            output = json.dumps(report.to_dict(), indent=2)
        else:
            output = report.to_text()

        print("\n" + output)

        if args.save:
            with open(args.save, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"\nReport saved to {args.save}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
