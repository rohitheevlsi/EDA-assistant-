"""
Testbench Generator - Phase 6
Step 1: Builds a guaranteed-compilable skeleton from the parsed port list.
Step 2: Uses the LLM to add meaningful stimulus and assertions on top.
"""

import os
import subprocess
import tempfile
from src.llm_engine import _get_client


import re as _re

def _is_param_width(w_str: str) -> bool:
    """Return True if the width string contains parameter identifiers (not pure numbers)."""
    # strip brackets if present: [7:0] -> 7:0
    inner = w_str.strip("[]")
    # If it contains any letter it's parameterised
    return bool(_re.search(r"[A-Za-z_]", inner))


def _port_type_to_verilog(port: dict) -> str:
    """Convert a port dict to a reg/wire declaration.
    
    If the width is parameterized (e.g. [WIDTH-1:0]), we fall back to a
    safe 8-bit default and add a comment so the testbench still compiles.
    """
    w_str = port.get("width_str", "")
    if w_str and _is_param_width(w_str):
        # Parameterized width — use 8 bits as safe default with a note
        safe_w = "[7:0] "
        comment = f"  // parameterized; defaulted from {w_str}"
    elif w_str:
        safe_w = w_str + " "
        comment = ""
    else:
        safe_w = ""
        comment = ""

    if port["direction"] in ("input", "inout"):
        return f"    reg {safe_w}{port['name']};{comment}"
    else:
        return f"    wire {safe_w}{port['name']};{comment}"


def generate_tb_skeleton(ir_summary: dict) -> str:
    """
    Generate a compilable testbench skeleton from the module's port list.
    This is deterministic and guaranteed to compile — no LLM involved.
    """
    mod_name = ir_summary["name"]
    ports = ir_summary["ports"]          # list of port name strings
    port_details = ir_summary.get("port_details", [])  # list of dicts with direction/width

    # Build declaration lines
    decl_lines = []
    conn_lines = []

    if port_details:
        for p in port_details:
            decl_lines.append(_port_type_to_verilog(p))
            conn_lines.append(f"        .{p['name']}({p['name']})")
    else:
        # Fallback: treat everything as reg/wire by common naming conventions
        clk_names = {"clk", "clock", "clk_i"}
        rst_names = {"rst", "reset", "rst_n", "rst_i"}
        for p in ports:
            plow = p.lower()
            if plow in clk_names or plow in rst_names:
                decl_lines.append(f"    reg  {p};")
            else:
                decl_lines.append(f"    reg  {p};   // TODO: set reg/wire based on direction")
            conn_lines.append(f"        .{p}({p})")

    conn_str = ",\n".join(conn_lines)
    decls_str = "\n".join(decl_lines)

    skeleton = f"""`timescale 1ns/1ps

module tb_{mod_name};

{decls_str}

    // Instantiate DUT
    {mod_name} dut (
{conn_str}
    );

    // Clock generation
    initial begin
        // TODO: set clock period for your design
        // clk = 0;
        // forever #5 clk = ~clk;
    end

    initial begin
        $dumpfile("tb_{mod_name}.vcd");
        $dumpvars(0, tb_{mod_name});

        // TODO: add stimulus here
        #100;
        $finish;
    end

endmodule
"""
    return skeleton


def llm_enhance_tb(module_name: str, ir_summary: dict, skeleton: str) -> str:
    """
    Ask the LLM to enhance the skeleton with meaningful stimulus and assertions.
    Returns the enhanced testbench string.
    """
    try:
        client = _get_client()
    except ValueError as e:
        return skeleton  # fall back to skeleton if no API key

    prompt = f"""You are a Verilog testbench expert.

Below is an auto-generated skeleton testbench for the Verilog module '{module_name}'.
The module has these ports: {', '.join(ir_summary.get('ports', []))}.

Your task: Fill in the skeleton with:
1. Realistic clock generation (if clk/clock port exists).
2. Reset assertion/de-assertion (if rst/rst_n exists).
3. 3-5 representative stimulus sequences that exercise interesting behaviour.
4. At least 2 `$display` checks or `if (x !== y) $error(...)` assertions.

RULES:
- Return ONLY valid Verilog code — no markdown, no explanation text.
- Keep the module instantiation exactly as-is. Only fill in the initial blocks.
- Do NOT change port names or module name.

SKELETON:
{skeleton}
"""

    from src.llm_engine import _generate
    try:
        text, model = _generate(client, prompt)
        text = text.strip()
        # Strip any accidental markdown code fences
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return text
    except Exception as e:
        print(f"[DEBUG] LLM testbench enhancement failed: {e}")
        return skeleton


def run_iverilog_check(tb_code: str, module_verilog: str, module_name: str) -> tuple[bool, str, str]:
    """
    Compile the testbench + module with iverilog and run the simulation using vvp.
    Returns (success, compile_output, simulation_output).
    """
    from src.toolchain import run_tool
    with tempfile.TemporaryDirectory() as tmpdir:
        tb_path = os.path.join(tmpdir, f"tb_{module_name}.v")
        mod_path = os.path.join(tmpdir, f"{module_name}.v")
        out_path = os.path.join(tmpdir, "sim.out")

        with open(tb_path, "w") as f:
            f.write(tb_code)
        with open(mod_path, "w") as f:
            f.write(module_verilog)

        result = run_tool("iverilog", ["-o", out_path, tb_path, mod_path])
        success = result.returncode == 0
        compile_output = (result.stdout + result.stderr).strip()

        if not success:
            return False, compile_output, ""

        # Run simulation
        result_sim = run_tool("vvp", [out_path])
        simulation_output = (result_sim.stdout + result_sim.stderr).strip()

        return True, compile_output, simulation_output


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from src.parser_ir import parse_verilog, summarize_ast

    fp = sys.argv[1] if len(sys.argv) > 1 else "tests/verilog/adder.v"
    ast = parse_verilog(fp)
    ir = summarize_ast(ast)

    print("=== SKELETON ===")
    skel = generate_tb_skeleton(ir)
    print(skel)

    print("=== LLM-ENHANCED ===")
    enhanced = llm_enhance_tb(ir["name"], ir, skel)
    print(enhanced)

    with open(fp) as f:
        mod_src = f.read()
    ok, compile_out, sim_out = run_iverilog_check(enhanced, mod_src, ir["name"])
    print(f"\n=== COMPILE CHECK: {'PASS' if ok else 'FAIL'} ===")
    if compile_out:
        print("Compile output:")
        print(compile_out)
    if sim_out:
        print("Simulation output:")
        print(sim_out)

