"""
Synthesis Engine - Phase 5 (Cross-Platform)
Shells out to Yosys and parses real gate-count/area statistics, plus writes JSON netlist.
CONSTRAINT: All numbers in this module come from Yosys output, never from the LLM.
"""

import os
import re
import tempfile
import json
from dataclasses import dataclass, field
from typing import Optional
from src.toolchain import run_tool


@dataclass
class SynthesisResult:
    module_name: str
    gates: dict = field(default_factory=dict)      # {cell_type: count}
    total_cells: int = 0
    wires: int = 0
    wire_bits: int = 0
    memories: int = 0
    memory_bits: int = 0
    processes: int = 0
    cells: int = 0
    warnings: list = field(default_factory=list)
    raw_output: str = ""
    error: Optional[str] = None
    netlist_json: Optional[dict] = None            # Parsed JSON netlist structure


def _run_yosys(script: str) -> tuple[str, str, int]:
    """Run a Yosys script string and return (stdout, stderr, returncode)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ys", delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        # Run directly using cross-platform toolchain utility (no -q: need stat output)
        result = run_tool("yosys", [script_path])
        # Yosys writes output to stdout when given a script file
        combined = result.stdout + result.stderr
        return combined, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), -1
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def run_synthesis(filepath: str, synth_options: Optional[dict] = None) -> SynthesisResult:
    """
    Run Yosys synthesis on a Verilog file and return real stats.
    Supports optional synthesis parameters (synth_options dict) for PSO design exploration.
    Generates a structured netlist JSON file for schematic visualization.
    """
    options = synth_options or {}
    flatten_str = "-flatten" if options.get("flatten", True) else ""

    # FSM encoding
    fsm_enc = options.get("fsm_encoding", "auto")
    fsm_cmd = f"fsm -encoding {fsm_enc}" if fsm_enc != "auto" else ""

    # Resource sharing
    share_cmd = "share" if options.get("resource_sharing", False) else ""

    # ABC strategy
    abc_strat = options.get("abc_strategy", "default")
    if abc_strat == "fast":
        abc_cmd = "abc -fast"
    elif abc_strat == "dff":
        abc_cmd = "abc -dff"
    elif abc_strat == "all":
        abc_cmd = "abc -g ALL"
    elif abc_strat == "simple":
        abc_cmd = "abc -g SIMPLE"
    else:
        abc_cmd = "abc"

    # Escape backslashes for Yosys script
    fpath_escaped = filepath.replace("\\", "/")

    # Create a temporary file to store the JSON netlist output
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json_path = f.name
    try:
        os.unlink(json_path) # Let Yosys create it
    except Exception:
        pass

    json_path_escaped = json_path.replace("\\", "/")

    script_lines = [f'read_verilog "{fpath_escaped}"']
    if share_cmd:
        script_lines.append(share_cmd)
    if fsm_cmd:
        script_lines.append(fsm_cmd)
    script_lines.append(f"synth -auto-top {flatten_str}")
    if abc_cmd and abc_cmd != "abc":
        script_lines.append(abc_cmd)
    script_lines.append("stat")
    script_lines.append(f'write_json "{json_path_escaped}"')

    yosys_script = "\n".join(script_lines) + "\n"

    stdout, stderr, rc = _run_yosys(yosys_script)

    result = SynthesisResult(module_name=os.path.basename(filepath))
    result.raw_output = stdout + "\n" + stderr

    # Parse %Error lines
    for line in (stdout + stderr).splitlines():
        if "%Error" in line or "ERROR" in line:
            result.warnings.append(line.strip())

    if rc != 0 and not stdout.strip():
        result.error = stderr.strip() or "Unknown Yosys error"
        return result

    # Read and parse JSON netlist if generated successfully
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                result.netlist_json = json.load(jf)
        except Exception as je:
            result.warnings.append(f"Failed to parse Yosys JSON netlist: {je}")
        finally:
            try:
                os.unlink(json_path)
            except Exception:
                pass

    # Parse classic Yosys stat text output
    # Find the LAST stat block (after synth)
    in_stat = False
    for line in stdout.splitlines():
        if re.match(r'=== .+ ===', line):
            in_stat = True
        if not in_stat:
            continue

        m = re.match(r'\s+(\d+) wires$', line)
        if m:
            result.wires = int(m.group(1))
        m = re.match(r'\s+(\d+) wire bits$', line)
        if m:
            result.wire_bits = int(m.group(1))
        m = re.match(r'\s+(\d+) memories$', line)
        if m:
            result.memories = int(m.group(1))
        m = re.match(r'\s+(\d+) memory bits$', line)
        if m:
            result.memory_bits = int(m.group(1))
        m = re.match(r'\s+(\d+) processes$', line)
        if m:
            result.processes = int(m.group(1))
        m = re.match(r'\s+(\d+) cells$', line)
        if m:
            result.cells = int(m.group(1))
            result.total_cells = result.cells
        # Cell type breakdown e.g.:   1   $_AND_
        m = re.match(r'\s+(\d+)\s+(\$\S+)', line)
        if m:
            result.gates[m.group(2)] = int(m.group(1))

    return result


def format_synthesis_report(result: SynthesisResult) -> str:
    if result.error:
        return f"  Yosys Error: {result.error}"
    lines = [
        f"  Wires: {result.wires}  (bits: {result.wire_bits})",
        f"  Memories: {result.memories}  (bits: {result.memory_bits})",
        f"  Processes: {result.processes}",
        f"  Total cells: {result.total_cells}",
    ]
    if result.gates:
        lines.append("  Cell breakdown:")
        for cell, count in sorted(result.gates.items()):
            lines.append(f"    {cell:<30} {count}")
    if result.warnings:
        lines.append("  Yosys warnings:")
        for w in result.warnings:
            lines.append(f"    {w}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    fp = sys.argv[1] if len(sys.argv) > 1 else "tests/verilog/adder.v"
    r = run_synthesis(fp)
    print(format_synthesis_report(r))
