import os
import sys
import pytest

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser_ir import parse_verilog, summarize_ast
from src.complexity import compute_complexity

VERILOG_DIR = os.path.join(os.path.dirname(__file__), "verilog")


def _get_module(filepath):
    """Helper: parse file and return (ast, first_module_dict)."""
    ast = parse_verilog(filepath)
    ir = summarize_ast(ast)
    ir_mod = ir["modules"][0] if ir["modules"] else {}
    return ast, ir_mod


def test_adder_complexity():
    ast, ir_mod = _get_module(os.path.join(VERILOG_DIR, "adder.v"))
    metrics = compute_complexity(ast, ir_mod)

    assert metrics["port_count"] == 4
    assert metrics["clock_domain_count"] == 0
    # Simple adder has no conditionals → approximated cyclomatic = 1
    assert metrics["approximated_cyclomatic_complexity"] == 1


def test_counter_gray_complexity():
    ast, ir_mod = _get_module(os.path.join(VERILOG_DIR, "counter_gray.v"))
    metrics = compute_complexity(ast, ir_mod)

    assert metrics["clock_domain_count"] == 1
    assert "clk" in metrics["clock_domains"]
    # Gray counter has registers → register bits must be non-zero
    assert metrics["register_bits"] > 0


def test_alu_complexity():
    ast, ir_mod = _get_module(os.path.join(VERILOG_DIR, "alu_8bit.v"))
    metrics = compute_complexity(ast, ir_mod)

    # ALU has case/if → cyclomatic > 1
    assert metrics["approximated_cyclomatic_complexity"] > 1
    assert metrics["case_statements"] > 0
