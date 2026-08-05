"""
Report Aggregator - Phase 7 (Enhanced)
Combines IR, Lint, LLM, Synthesis, Complexity, Power/Timing, and Quality Score
results into one structured report object.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EDAReport:
    filepath: str
    module_name: str
    ir_summary: dict = field(default_factory=dict)
    lint_warnings: list = field(default_factory=list)     # custom linter
    verilator_warnings: str = ""                          # raw verilator output
    llm_explanation: str = ""
    synthesis: Optional[object] = None                    # SynthesisResult
    testbench_skeleton: str = ""
    testbench_enhanced: str = ""
    testbench_compiles: Optional[bool] = None
    testbench_compile_output: str = ""
    testbench_simulation_success: Optional[bool] = None
    testbench_simulation_output: str = ""
    # New fields
    complexity_metrics: dict = field(default_factory=dict)
    power_timing: dict = field(default_factory=dict)
    quality_score: dict = field(default_factory=dict)
    source_code: str = ""

    def to_text(self) -> str:
        """Render the full aggregated report as a plain-text string."""
        sep = "=" * 60
        lines = [
            sep,
            f"EDA ASSISTANT REPORT",
            f"File:   {self.filepath}",
            f"Module: {self.module_name}",
            sep,
            "",
            "=== IR SUMMARY ===",
            f"  Ports:         {', '.join(self.ir_summary.get('ports', []))}",
            f"  Signals:       {', '.join(self.ir_summary.get('signals', [])) or '(none)'}",
            f"  Always Blocks: {self.ir_summary.get('always_blocks', 0)}",
            "",
            "=== STATIC LINT (Custom) ===",
        ]
        if self.lint_warnings:
            for w in self.lint_warnings:
                lines.append(f"  {w}")
        else:
            lines.append("  No issues found.")

        lines += ["", "=== VERILATOR LINT ==="]
        if self.verilator_warnings.strip():
            for line in self.verilator_warnings.splitlines():
                if line.strip():
                    lines.append(f"  {line.strip()}")
        else:
            lines.append("  No issues found.")

        # Complexity metrics
        if self.complexity_metrics:
            from src.complexity import format_complexity_report
            lines += ["", "=== DESIGN COMPLEXITY METRICS ===",
                       format_complexity_report(self.complexity_metrics)]

        # Power/Timing/Area
        if self.power_timing:
            from src.power_timing import format_power_timing_report
            lines += ["", "=== POWER / TIMING / AREA (45nm Estimate) ===",
                       format_power_timing_report(self.power_timing)]

        # Quality Score
        if self.quality_score:
            from src.quality_score import format_quality_report
            lines += ["", "=== RTL QUALITY SCORE ===",
                       format_quality_report(self.quality_score)]

        lines += ["", "=== LLM ANALYSIS ===", self.llm_explanation]

        if self.synthesis:
            from src.synthesis import format_synthesis_report
            lines += ["", "=== SYNTHESIS STATS (Yosys) ===",
                      format_synthesis_report(self.synthesis)]

        if self.testbench_skeleton:
            status = ""
            if self.testbench_compiles is not None:
                status = " [COMPILES OK]" if self.testbench_compiles else " [COMPILE FAIL]"
            lines += ["", f"=== TESTBENCH{status} ===", self.testbench_enhanced or self.testbench_skeleton]
            
            if self.testbench_compiles and self.testbench_simulation_output:
                lines += ["", "=== SIMULATION LOG ===", self.testbench_simulation_output]

        lines += ["", sep]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict for the web UI."""
        synth_dict = None
        if self.synthesis:
            s = self.synthesis
            synth_dict = {
                "module_name": s.module_name,
                "gates": s.gates,
                "total_cells": s.total_cells,
                "wires": s.wires,
                "wire_bits": s.wire_bits,
                "error": s.error,
                "warnings": s.warnings,
            }
        return {
            "filepath": self.filepath,
            "module_name": self.module_name,
            "ir_summary": self.ir_summary,
            "lint_warnings": self.lint_warnings,
            "verilator_warnings": self.verilator_warnings,
            "llm_explanation": self.llm_explanation,
            "synthesis": synth_dict,
            "testbench": self.testbench_enhanced or self.testbench_skeleton,
            "testbench_compiles": self.testbench_compiles,
            "testbench_simulation_success": self.testbench_simulation_success,
            "testbench_simulation_output": self.testbench_simulation_output,
            "complexity_metrics": self.complexity_metrics,
            "power_timing": self.power_timing,
            "quality_score": self.quality_score,
        }
