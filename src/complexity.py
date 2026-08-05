"""
Design Complexity Metrics Engine
Computes quantitative VLSI design metrics from the parsed IR and AST.
"""

from pyverilog.vparser.parser import parse


def _count_nodes(node, type_name):
    """Count AST nodes of a given type recursively."""
    count = 1 if type(node).__name__ == type_name else 0
    if hasattr(node, 'children'):
        for child in node.children():
            count += _count_nodes(child, type_name)
    return count


def _count_states(ast):
    """Detect FSM states by finding localparam/parameter declarations with binary/integer values."""
    states = []
    def find_params(node):
        if type(node).__name__ in ('Parameter', 'Localparam'):
            states.append(node.name)
        if hasattr(node, 'children'):
            for child in node.children():
                find_params(child)
    find_params(ast)
    return states


def _count_case_branches(node):
    """Count total case branches (transitions) recursively."""
    count = 0
    if type(node).__name__ == 'CaseStatement':
        count += len(node.caselist) if node.caselist else 0
    if hasattr(node, 'children'):
        for child in node.children():
            count += _count_case_branches(child)
    return count


def _count_if_depth(node, current_depth=0):
    """Calculate max nesting depth of if/else statements."""
    max_depth = current_depth
    if type(node).__name__ == 'IfStatement':
        current_depth += 1
        max_depth = max(max_depth, current_depth)
        if node.true_statement:
            max_depth = max(max_depth, _count_if_depth(node.true_statement, current_depth))
        if node.false_statement:
            max_depth = max(max_depth, _count_if_depth(node.false_statement, current_depth))
    elif hasattr(node, 'children'):
        for child in node.children():
            max_depth = max(max_depth, _count_if_depth(child, current_depth))
    return max_depth


def _estimate_register_bits(ast):
    """Estimate total register bits from Reg declarations."""
    total_bits = 0
    def find_regs(node):
        nonlocal total_bits
        if type(node).__name__ == 'Reg':
            if node.width:
                from pyverilog.ast_code_generator.codegen import ASTCodeGenerator
                cg = ASTCodeGenerator()
                w_str = cg.visit(node.width).strip().strip('[]')
                parts = w_str.split(':')
                if len(parts) == 2:
                    try:
                        msb = int(parts[0])
                        lsb = int(parts[1])
                        total_bits += abs(msb - lsb) + 1
                    except ValueError:
                        total_bits += 8  # parameterized, assume 8
                else:
                    total_bits += 1
            else:
                total_bits += 1
            # Check for memory arrays (e.g., reg [7:0] mem [0:15])
            if getattr(node, 'length', None):
                cg = ASTCodeGenerator()
                l_str = cg.visit(node.length).strip().strip('[]')
                parts = l_str.split(':')
                if len(parts) == 2:
                    try:
                        hi = int(parts[0])
                        lo = int(parts[1])
                        depth = abs(hi - lo) + 1
                        total_bits *= depth
                    except ValueError:
                        total_bits *= 8
        if hasattr(node, 'children'):
            for child in node.children():
                find_regs(child)
    find_regs(ast)
    return total_bits


def _detect_clock_domains(ast):
    """Detect distinct clock domains from always block sensitivity lists."""
    domains = set()
    rst_names = {'rst_n', 'rst', 'reset', 'arst_n', 'arst'}
    def find_clocks(node):
        if type(node).__name__ == 'Always':
            if node.sens_list:
                for sens in node.sens_list.list:
                    if sens.type in ('posedge', 'negedge'):
                        sig = sens.sig
                        if type(sig).__name__ == 'Identifier':
                            if sig.name.lower() not in rst_names:
                                domains.add(sig.name)
        if hasattr(node, 'children'):
            for child in node.children():
                find_clocks(child)
    find_clocks(ast)
    return domains


def _estimate_memory_bits(ast):
    """Estimate total memory bits from reg arrays."""
    total = 0
    def find_mems(node):
        nonlocal total
        if type(node).__name__ == 'Reg' and getattr(node, 'length', None):
            from pyverilog.ast_code_generator.codegen import ASTCodeGenerator
            cg = ASTCodeGenerator()
            w_bits = 1
            if node.width:
                w_str = cg.visit(node.width).strip().strip('[]')
                parts = w_str.split(':')
                if len(parts) == 2:
                    try:
                        w_bits = abs(int(parts[0]) - int(parts[1])) + 1
                    except ValueError:
                        w_bits = 8
            l_str = cg.visit(node.length).strip().strip('[]')
            parts = l_str.split(':')
            if len(parts) == 2:
                try:
                    depth = abs(int(parts[0]) - int(parts[1])) + 1
                    total += w_bits * depth
                except ValueError:
                    total += w_bits * 8
        if hasattr(node, 'children'):
            for child in node.children():
                find_mems(child)
    find_mems(ast)
    return total


def compute_complexity(ast, ir_summary):
    """
    Compute design complexity metrics.
    Returns a dict with all metrics.
    """
    mod = ir_summary if isinstance(ir_summary, dict) and 'name' in ir_summary else {}

    # Basic counts
    n_ports = len(mod.get('ports', []))
    n_signals = len(mod.get('signals', []))
    n_always = mod.get('always_blocks', 0)

    # AST-derived metrics
    n_if = _count_nodes(ast, 'IfStatement')
    n_case = _count_nodes(ast, 'CaseStatement')
    case_branches = _count_case_branches(ast)
    max_if_depth = _count_if_depth(ast)
    register_bits = _estimate_register_bits(ast)
    clock_domains = _detect_clock_domains(ast)
    memory_bits = _estimate_memory_bits(ast)

    # Cyclomatic complexity: E - N + 2P
    # Approximate: each if adds 1, each case branch adds 1
    cyclomatic = 1 + n_if + case_branches

    # FSM state count from parameters
    fsm_states = len(_count_states(ast))

    # Composite complexity score (0-100)
    score = min(100, int(
        cyclomatic * 3 +
        n_always * 5 +
        n_ports * 1.5 +
        max_if_depth * 4 +
        len(clock_domains) * 10 +
        (1 if memory_bits > 0 else 0) * 10
    ))

    return {
        'port_count': n_ports,
        'signal_count': n_signals,
        'always_blocks': n_always,
        'if_statements': n_if,
        'case_statements': n_case,
        'case_branches': case_branches,
        'max_nesting_depth': max_if_depth,
        'cyclomatic_complexity': cyclomatic,
        'register_bits': register_bits,
        'memory_bits': memory_bits,
        'clock_domains': sorted(clock_domains),
        'clock_domain_count': len(clock_domains),
        'fsm_parameters': fsm_states,
        'complexity_score': score,
        'complexity_grade': _grade(score),
    }


def _grade(score):
    if score <= 15:
        return 'Simple'
    elif score <= 35:
        return 'Moderate'
    elif score <= 60:
        return 'Complex'
    elif score <= 80:
        return 'Very Complex'
    else:
        return 'Highly Complex'


def format_complexity_report(metrics):
    lines = [
        f"  Ports: {metrics['port_count']}   Signals: {metrics['signal_count']}   Always Blocks: {metrics['always_blocks']}",
        f"  If Statements: {metrics['if_statements']}   Case Statements: {metrics['case_statements']}   Branches: {metrics['case_branches']}",
        f"  Max Nesting Depth: {metrics['max_nesting_depth']}",
        f"  Cyclomatic Complexity: {metrics['cyclomatic_complexity']}",
        f"  Register Bits: {metrics['register_bits']}   Memory Bits: {metrics['memory_bits']}",
        f"  Clock Domains: {', '.join(metrics['clock_domains']) or '(none)'}  ({metrics['clock_domain_count']})",
        f"  Complexity Score: {metrics['complexity_score']}/100 ({metrics['complexity_grade']})",
    ]
    return "\n".join(lines)
