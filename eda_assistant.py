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


def analyze(filepath: str, use_llm: bool = True, use_synth: bool = True, use_tb: bool = True) -> EDAReport:
    """Run the full EDA analysis pipeline on a single Verilog file."""

    print(f"\n[1/8] Parsing {filepath}...")
    ast = parse_verilog(filepath)
    ir = summarize_ast(ast)
    module_name = ir["modules"][0]["name"] if ir["modules"] else os.path.basename(filepath)
    ir_mod = ir["modules"][0] if ir["modules"] else {}

    # Read source code
    with open(filepath, encoding="utf-8", errors="replace") as f:
        source_code = f.read()

    report = EDAReport(filepath=filepath, module_name=module_name,
                       ir_summary=ir_mod, source_code=source_code)

    print(f"[2/8] Running static lint checks (10 rules)...")
    report.lint_warnings = lint_ast(ast)
    report.verilator_warnings = run_verilator_lint(filepath)

    print(f"[3/8] Computing design complexity metrics...")
    report.complexity_metrics = compute_complexity(ast, ir_mod)

    if use_synth:
        print(f"[4/8] Running Yosys synthesis...")
        report.synthesis = run_synthesis(filepath)
    else:
        print(f"[4/8] Synthesis skipped.")

    print(f"[5/8] Estimating power / timing / area...")
    if report.synthesis:
        report.power_timing = estimate_power_timing_area(
            report.synthesis, report.complexity_metrics)
    else:
        report.power_timing = {'error': 'Synthesis skipped'}

    if use_llm:
        print(f"[6/8] Querying Gemini LLM for explanation...")
        report.llm_explanation = generate_explanation(module_name, ir_mod, report.lint_warnings)
    else:
        report.llm_explanation = "(LLM skipped)"
        print(f"[6/8] LLM skipped.")

    if use_tb:
        print(f"[7/8] Generating testbench...")
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
        print(f"[7/8] Testbench generation skipped.")

    print(f"[8/8] Computing RTL quality score...")
    report.quality_score = compute_quality_score(
        report.lint_warnings,
        report.complexity_metrics,
        report.synthesis,
        report.testbench_compiles,
        report.testbench_simulation_output,
        report.verilator_warnings,
    )

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
