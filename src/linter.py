"""
Expanded Linter — 10 VLSI-Grade Rules
Original: LATCH, MULTI-DRIVEN
New: CDC-CROSSING, BLOCKING-IN-SEQ, NONBLOCKING-IN-COMB, UNDRIVEN-PORT,
     UNUSED-SIGNAL, NO-DEFAULT-CASE-SEQ
"""

import os
import subprocess
from pyverilog.vparser.parser import parse
from pyverilog.vparser.ast import Node


def get_assigned_signals(node, signals=None):
    if signals is None:
        signals = set()
    node_type = type(node).__name__
    if node_type in ('BlockingSubstitution', 'NonblockingSubstitution', 'Assign'):
        left = node.left.var
        if type(left).__name__ == 'Identifier':
            signals.add(left.name)
        elif type(left).__name__ in ('Pointer', 'Partselect'):
            if type(left.var).__name__ == 'Identifier':
                signals.add(left.var.name)
    for child in node.children():
        get_assigned_signals(child, signals)
    return signals


def is_combinational(always_node):
    if always_node.sens_list:
        for sens in always_node.sens_list.list:
            if sens.type in ('posedge', 'negedge'):
                return False
    return True


def get_read_signals(node, signals=None):
    if signals is None:
        signals = set()
    node_type = type(node).__name__
    if node_type == 'Identifier':
        signals.add(node.name)
    elif node_type in ('BlockingSubstitution', 'NonblockingSubstitution'):
        if node.right:
            get_read_signals(node.right.var if hasattr(node.right, 'var') else node.right, signals)
        left = node.left.var
        if type(left).__name__ in ('Pointer', 'Partselect'):
            if hasattr(left, 'ptr'):
                get_read_signals(left.ptr, signals)
        return signals
    for child in node.children():
        get_read_signals(child, signals)
    return signals


def find_conditional_assignments(node, assigned=None):
    if assigned is None:
        assigned = set()
    node_type = type(node).__name__
    if node_type in ('BlockingSubstitution', 'NonblockingSubstitution'):
        left = node.left.var
        if type(left).__name__ == 'Identifier':
            assigned.add(left.name)
        elif type(left).__name__ in ('Pointer', 'Partselect'):
            if type(left.var).__name__ == 'Identifier':
                assigned.add(left.var.name)
    for child in node.children():
        find_conditional_assignments(child, assigned)
    return assigned


def check_latches(block_node, default_assigned=None, warnings=None):
    if default_assigned is None:
        default_assigned = set()
    if warnings is None:
        warnings = []
    node_type = type(block_node).__name__
    if node_type == 'Block':
        current_defaults = set(default_assigned)
        for stmt in block_node.statements:
            stmt_type = type(stmt).__name__
            if stmt_type in ('BlockingSubstitution', 'NonblockingSubstitution'):
                left = stmt.left.var
                if type(left).__name__ == 'Identifier':
                    current_defaults.add(left.name)
                elif type(left).__name__ in ('Pointer', 'Partselect'):
                    if type(left.var).__name__ == 'Identifier':
                        current_defaults.add(left.var.name)
            elif stmt_type in ('IfStatement', 'CaseStatement'):
                check_latches(stmt, current_defaults, warnings)
    elif node_type == 'IfStatement':
        if not block_node.false_statement:
            cond_assigned = find_conditional_assignments(block_node.true_statement)
            if not cond_assigned.issubset(default_assigned):
                warnings.append("Incomplete 'if' statement without 'else' branch")
        else:
            check_latches(block_node.true_statement, default_assigned, warnings)
            check_latches(block_node.false_statement, default_assigned, warnings)
    elif node_type == 'CaseStatement':
        has_default = any(type(c).__name__ == 'Block' or c.cond is None for c in block_node.caselist)
        if not has_default:
            cond_assigned = set()
            for c in block_node.caselist:
                cond_assigned.update(find_conditional_assignments(c))
            if not cond_assigned.issubset(default_assigned):
                warnings.append("Incomplete 'case' statement without 'default' branch")
        for c in block_node.caselist:
            check_latches(c, default_assigned, warnings)
    else:
        for child in block_node.children():
            check_latches(child, default_assigned, warnings)
    return warnings


def _get_clock_signals(always_node):
    clocks = set()
    if always_node.sens_list:
        for sens in always_node.sens_list.list:
            if sens.type in ('posedge', 'negedge'):
                sig = sens.sig
                if type(sig).__name__ == 'Identifier':
                    clocks.add(sig.name)
    return clocks


def _get_assignment_types(node, types=None):
    if types is None:
        types = {'blocking': set(), 'nonblocking': set()}
    node_type = type(node).__name__
    if node_type == 'BlockingSubstitution':
        left = node.left.var
        name = None
        if type(left).__name__ == 'Identifier':
            name = left.name
        elif type(left).__name__ in ('Pointer', 'Partselect'):
            if type(left.var).__name__ == 'Identifier':
                name = left.var.name
        if name:
            types['blocking'].add(name)
    elif node_type == 'NonblockingSubstitution':
        left = node.left.var
        name = None
        if type(left).__name__ == 'Identifier':
            name = left.name
        elif type(left).__name__ in ('Pointer', 'Partselect'):
            if type(left.var).__name__ == 'Identifier':
                name = left.var.name
        if name:
            types['nonblocking'].add(name)
    for child in node.children():
        _get_assignment_types(child, types)
    return types


def _find_case_no_default_seq(node, warnings=None):
    if warnings is None:
        warnings = []
    node_type = type(node).__name__
    if node_type == 'CaseStatement':
        has_default = False
        for ci in node.caselist:
            if ci.cond is None:
                has_default = True
                break
        if not has_default:
            warnings.append("'case' without 'default' in sequential block")
    for child in node.children():
        _find_case_no_default_seq(child, warnings)
    return warnings


def lint_ast(ast):
    results = []
    if not ast.description:
        return results
    for desc in ast.description.definitions:
        if type(desc).__name__ != 'ModuleDef':
            continue
        mod_name = desc.name
        always_blocks = [item for item in desc.items if type(item).__name__ == 'Always']

        # 1. MULTI-DRIVEN
        signal_drivers = {}
        for idx, always in enumerate(always_blocks):
            assigned = get_assigned_signals(always.statement)
            for sig in assigned:
                signal_drivers.setdefault(sig, []).append(idx)
        for sig, drivers in signal_drivers.items():
            if len(drivers) > 1:
                results.append(f"[MULTI-DRIVEN] Signal '{sig}' is driven in multiple always blocks ({len(drivers)} blocks) in module '{mod_name}'.")

        # 2. LATCH
        for always in always_blocks:
            if is_combinational(always):
                for inc in check_latches(always.statement):
                    results.append(f"[LATCH] {inc} in combinational always block in module '{mod_name}'. This infers a latch.")

        # 3. CDC-CROSSING
        clk_drv = {}
        clk_rd = {}
        for always in always_blocks:
            clks = _get_clock_signals(always)
            if not clks:
                continue
            # Filter out reset signals
            rst_names = {'rst_n', 'rst', 'reset', 'arst_n', 'arst'}
            clks = clks - rst_names
            if not clks:
                continue
            for sig in get_assigned_signals(always.statement):
                clk_drv.setdefault(sig, set()).update(clks)
            for sig in get_read_signals(always.statement):
                clk_rd.setdefault(sig, set()).update(clks)
        for sig in clk_drv:
            if sig in clk_rd:
                cross = clk_rd[sig] - clk_drv[sig]
                if cross:
                    results.append(
                        f"[CDC-CROSSING] Signal '{sig}' driven by {{{', '.join(sorted(clk_drv[sig]))}}} "
                        f"but read in {{{', '.join(sorted(cross))}}} in module '{mod_name}'. "
                        f"Potential metastability — add a synchronizer.")

        # 4. BLOCKING-IN-SEQ
        for always in always_blocks:
            if not is_combinational(always):
                at = _get_assignment_types(always.statement)
                if at['blocking']:
                    sigs = ', '.join(sorted(at['blocking']))
                    results.append(f"[BLOCKING-IN-SEQ] Blocking assignment(s) to '{sigs}' in clocked always block in module '{mod_name}'. Use non-blocking (<=).")

        # 5. NONBLOCKING-IN-COMB
        for always in always_blocks:
            if is_combinational(always):
                at = _get_assignment_types(always.statement)
                if at['nonblocking']:
                    sigs = ', '.join(sorted(at['nonblocking']))
                    results.append(f"[NONBLOCKING-IN-COMB] Non-blocking assignment(s) to '{sigs}' in combinational always block in module '{mod_name}'. Use blocking (=).")

        # 6. UNDRIVEN-PORT
        def find_outputs(node):
            outs = set()
            if type(node).__name__ == 'Output':
                outs.add(node.name)
            if hasattr(node, 'children'):
                for child in node.children():
                    outs.update(find_outputs(child))
            return outs
        output_ports = find_outputs(desc)
        all_assigned = set()
        for always in always_blocks:
            all_assigned.update(get_assigned_signals(always.statement))
        for item in desc.items:
            if type(item).__name__ == 'Assign':
                all_assigned.update(get_assigned_signals(item))
        for port in sorted(output_ports):
            if port not in all_assigned:
                results.append(f"[UNDRIVEN-PORT] Output port '{port}' is never assigned in module '{mod_name}'.")

        # 7. UNUSED-SIGNAL
        declared = set()
        for item in desc.items:
            if type(item).__name__ == 'Decl':
                for d in item.list:
                    if type(d).__name__ in ('Wire', 'Reg'):
                        declared.add(d.name)
        all_read = set()
        for always in always_blocks:
            all_read.update(get_read_signals(always.statement))
        for item in desc.items:
            if type(item).__name__ == 'Assign':
                all_read.update(get_read_signals(item))
        for sig in sorted(declared):
            if sig not in all_read and sig not in output_ports and sig not in all_assigned:
                results.append(f"[UNUSED-SIGNAL] Signal '{sig}' is declared but never used in module '{mod_name}'.")

        # 8. NO-DEFAULT-CASE (sequential)
        for always in always_blocks:
            if not is_combinational(always):
                for w in _find_case_no_default_seq(always.statement):
                    results.append(f"[NO-DEFAULT-CASE] {w} in module '{mod_name}'. Add 'default' to prevent undefined behavior.")

    return results


def run_verilator_lint(filepath):
    from src.toolchain import run_tool
    try:
        # Use verilator_bin directly via run_tool
        result = run_tool("verilator_bin", ["--lint-only", "-Wall", "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-EOFNEWLINE", filepath])
        return result.stderr.strip() + "\n" + result.stdout.strip()
    except Exception as e:
        return f"Error running verilator: {e}"


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python linter.py <verilog_file>")
        return
    filepath = sys.argv[1]
    print(f"--- LINTING {os.path.basename(filepath)} ---")
    try:
        from pyverilog.vparser.parser import parse
        ast, directives = parse([filepath])
        custom_warnings = lint_ast(ast)
        print("Custom Linter Results:")
        if not custom_warnings:
            print("  No issues found.")
        else:
            for w in custom_warnings:
                print(f"  {w}")
    except Exception as e:
        print(f"  Failed to parse AST: {e}")
    print("\nVerilator Lint Results:")
    v_out = run_verilator_lint(filepath)
    if not v_out:
        print("  No issues found.")
    else:
        for line in v_out.split('\n'):
            if line.strip():
                print(f"  {line.strip()}")
    print("-" * 40)

if __name__ == '__main__':
    main()
