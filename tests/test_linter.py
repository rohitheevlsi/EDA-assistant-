import os
import sys
import pytest

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser_ir import parse_verilog
from src.linter import lint_ast

VERILOG_DIR = os.path.join(os.path.dirname(__file__), "verilog")


def test_latch_detection():
    filepath = os.path.join(VERILOG_DIR, "latch_bug.v")
    ast = parse_verilog(filepath)
    warnings = lint_ast(ast)
    
    # Assert we find a latch warning
    latch_warnings = [w for w in warnings if "[LATCH]" in w]
    assert len(latch_warnings) > 0, "Failed to detect inferred latch in latch_bug.v"


def test_multidriven_detection():
    filepath = os.path.join(VERILOG_DIR, "multidriven_bug.v")
    ast = parse_verilog(filepath)
    warnings = lint_ast(ast)
    
    # Assert we find a multi-driven warning
    md_warnings = [w for w in warnings if "[MULTI-DRIVEN]" in w]
    assert len(md_warnings) > 0, "Failed to detect multi-driven net in multidriven_bug.v"


def test_cdc_violation_detection():
    filepath = os.path.join(VERILOG_DIR, "cdc_violation.v")
    ast = parse_verilog(filepath)
    warnings = lint_ast(ast)
    
    # Assert we find a CDC warning
    cdc_warnings = [w for w in warnings if "[CDC-CROSSING]" in w]
    assert len(cdc_warnings) > 0, "Failed to detect clock domain crossing in cdc_violation.v"


def test_blocking_in_seq_detection():
    filepath = os.path.join(VERILOG_DIR, "blocking_seq_bug.v")
    ast = parse_verilog(filepath)
    warnings = lint_ast(ast)
    
    # Assert we find a blocking assignment in sequential block warning
    block_warnings = [w for w in warnings if "[BLOCKING-IN-SEQ]" in w]
    assert len(block_warnings) > 0, "Failed to detect blocking assignment in clocked block in blocking_seq_bug.v"


def test_clean_file_lints_clean():
    # alu_8bit should be clean of basic bugs
    filepath = os.path.join(VERILOG_DIR, "alu_8bit.v")
    ast = parse_verilog(filepath)
    warnings = lint_ast(ast)
    
    # Check that critical warnings are absent
    critical = [w for w in warnings if any(x in w for x in ["[LATCH]", "[MULTI-DRIVEN]", "[CDC-CROSSING]", "[BLOCKING-IN-SEQ]"])]
    assert len(critical) == 0, f"Clean file has unexpected critical warnings: {critical}"
