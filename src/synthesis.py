"""
Synthesis Engine - Phase 5
Shells out to Yosys and parses real gate-count/area statistics.
CONSTRAINT: All numbers in this module come from Yosys output, never from the LLM.
"""

import os
import subprocess
import re
import tempfile
from dataclasses import dataclass, field
from typing import Optional

YOSYS_BAT = r"E:\oss-cad-suite\environment.bat"


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


def _run_yosys(script: str) -> tuple[str, str, int]:
    """Run a Yosys script string and return (stdout, stderr, returncode)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ys", delete=False) as f:
        f.write(script)
        script_path = f.name

    cmd = ["cmd.exe", "/c", f"{YOSYS_BAT} && yosys {script_path}"]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # Yosys writes all output to stdout when given a file argument
        combined = result.stdout + result.stderr
        return combined, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), -1
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def run_synthesis(filepath: str) -> SynthesisResult:
    """
    Run Yosys synthesis on a Verilog file and return real stats.
    Uses generic gate library (synth with no tech target) to get technology-independent counts.
    """
    # Escape backslashes for Yosys script
    fpath_escaped = filepath.replace("\\", "/")

    yosys_script = f"""
read_verilog {fpath_escaped}
synth -flatten
stat
"""

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
