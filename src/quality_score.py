"""
RTL Quality Score Engine
Computes a 0-100 quality score based on lint results, coding style,
design structure, testability, and complexity balance.
Outputs a letter grade (A+ to F) with specific improvement recommendations.
"""


def compute_quality_score(lint_warnings, complexity_metrics, synth_result,
                          tb_compiles=None, tb_sim_output="", verilator_warnings=""):
    """
    Compute an RTL quality score from 0-100.

    Scoring breakdown:
      - Lint Cleanliness:   25 points
      - Coding Style:       20 points
      - Design Structure:   20 points
      - Testability:        15 points
      - Complexity Balance: 10 points
      - Documentation:      10 points

    Returns dict with score, grade, breakdown, and recommendations.
    """
    score = 0
    breakdown = {}
    recommendations = []

    # ── 1. LINT CLEANLINESS (25 pts) ──
    lint_score = 25
    n_warnings = len(lint_warnings) if lint_warnings else 0
    critical_count = sum(1 for w in (lint_warnings or [])
                         if any(tag in w for tag in ['[CDC-CROSSING]', '[MULTI-DRIVEN]']))
    style_count = sum(1 for w in (lint_warnings or [])
                      if any(tag in w for tag in ['[BLOCKING-IN-SEQ]', '[NONBLOCKING-IN-COMB]']))
    latch_count = sum(1 for w in (lint_warnings or []) if '[LATCH]' in w)
    other_count = n_warnings - critical_count - style_count - latch_count

    # Parse Verilator warnings
    v_warnings_count = 0
    v_errors_count = 0
    if verilator_warnings:
        for line in verilator_warnings.splitlines():
            if "%Warning-" in line:
                v_warnings_count += 1
            elif "%Error-" in line or "%Error:" in line:
                v_errors_count += 1

    lint_score -= critical_count * 8
    lint_score -= latch_count * 5
    lint_score -= style_count * 3
    lint_score -= other_count * 2
    lint_score -= v_warnings_count * 2
    lint_score -= v_errors_count * 10
    lint_score = max(0, lint_score)
    breakdown['lint_cleanliness'] = lint_score

    if v_warnings_count > 0:
        recommendations.append(f"Resolve {v_warnings_count} Verilator warning(s) to guarantee clean synthesis mapping.")
    if v_errors_count > 0:
        recommendations.append(f"Resolve {v_errors_count} Verilator error(s) — design will not compile or run in hardware.")

    if critical_count > 0:
        recommendations.append("FIX CRITICAL: CDC crossings and multi-driven nets must be resolved before tape-out.")
    if latch_count > 0:
        recommendations.append("Add 'else'/'default' branches to avoid inferred latches in combinational logic.")
    if style_count > 0:
        recommendations.append("Use non-blocking (<=) in sequential blocks, blocking (=) in combinational blocks.")

    # ── 2. CODING STYLE (20 pts) ──
    style_score = 20
    if style_count > 0:
        style_score -= style_count * 5
    if latch_count > 0:
        style_score -= latch_count * 3
    style_score = max(0, style_score)
    breakdown['coding_style'] = style_score

    # ── 3. DESIGN STRUCTURE (20 pts) ──
    struct_score = 20
    if complexity_metrics:
        # Penalize very deep nesting (>4 levels)
        depth = complexity_metrics.get('max_nesting_depth', 0)
        if depth > 4:
            struct_score -= (depth - 4) * 3
            recommendations.append(f"Reduce nesting depth (currently {depth}). Extract sub-modules for readability.")

        # Reward proper FSM structure
        cc = complexity_metrics.get('cyclomatic_complexity', 0)
        if cc > 20:
            struct_score -= 5
            recommendations.append("High cyclomatic complexity. Consider decomposing into sub-modules.")

        # CDC handling
        cdc_count = complexity_metrics.get('clock_domain_count', 0)
        if cdc_count > 1 and critical_count == 0:
            struct_score += 0  # no bonus, just don't penalize
        elif cdc_count > 1 and critical_count > 0:
            struct_score -= 5

    struct_score = max(0, min(20, struct_score))
    breakdown['design_structure'] = struct_score

    # ── 4. TESTABILITY (15 pts) ──
    test_score = 0
    if tb_compiles is True:
        test_score += 8
        if tb_sim_output:
            # Check for assertion passes
            sim_lower = tb_sim_output.lower()
            if 'error' not in sim_lower and 'fail' not in sim_lower:
                test_score += 7
            else:
                test_score += 3
                recommendations.append("Some testbench assertions failed. Review simulation log.")
        else:
            test_score += 4
    elif tb_compiles is False:
        test_score = 2
        recommendations.append("Testbench failed to compile. Review generated testbench for syntax errors.")
    else:
        test_score = 0
        recommendations.append("Enable testbench generation to improve testability score.")
    breakdown['testability'] = test_score

    # ── 5. COMPLEXITY BALANCE (10 pts) ──
    balance_score = 10
    if complexity_metrics:
        cs = complexity_metrics.get('complexity_score', 0)
        # Ideal range is 20-60 — not too simple, not too complex
        if cs < 10:
            balance_score -= 3
            recommendations.append("Design is very simple. Consider adding error handling or configurability.")
        elif cs > 70:
            balance_score -= 4
            recommendations.append("Design is very complex. Consider hierarchical decomposition.")
    breakdown['complexity_balance'] = max(0, balance_score)

    # ── 6. DOCUMENTATION (10 pts) ──
    # Since we can't read comments from the IR, give partial credit
    doc_score = 6  # base credit
    if complexity_metrics:
        if complexity_metrics.get('fsm_parameters', 0) > 0:
            doc_score += 2  # localparams used = self-documenting
        if complexity_metrics.get('port_count', 0) > 0:
            doc_score += 2
    breakdown['documentation'] = min(10, doc_score)

    # ── TOTAL ──
    score = sum(breakdown.values())
    grade = _letter_grade(score)

    return {
        'total_score': score,
        'max_score': 100,
        'grade': grade,
        'breakdown': breakdown,
        'recommendations': recommendations,
        'lint_warning_count': n_warnings,
    }


def _letter_grade(score):
    if score >= 95:
        return 'A+'
    elif score >= 90:
        return 'A'
    elif score >= 85:
        return 'A-'
    elif score >= 80:
        return 'B+'
    elif score >= 75:
        return 'B'
    elif score >= 70:
        return 'B-'
    elif score >= 65:
        return 'C+'
    elif score >= 60:
        return 'C'
    elif score >= 55:
        return 'C-'
    elif score >= 50:
        return 'D+'
    elif score >= 45:
        return 'D'
    elif score >= 40:
        return 'D-'
    else:
        return 'F'


def format_quality_report(qs):
    lines = [
        f"  Score: {qs['total_score']}/{qs['max_score']}  Grade: {qs['grade']}",
        f"  Breakdown:",
    ]
    labels = {
        'lint_cleanliness': 'Lint Cleanliness',
        'coding_style': 'Coding Style',
        'design_structure': 'Design Structure',
        'testability': 'Testability',
        'complexity_balance': 'Complexity Balance',
        'documentation': 'Documentation',
    }
    max_pts = {
        'lint_cleanliness': 25,
        'coding_style': 20,
        'design_structure': 20,
        'testability': 15,
        'complexity_balance': 10,
        'documentation': 10,
    }
    for key, label in labels.items():
        val = qs['breakdown'].get(key, 0)
        mx = max_pts.get(key, 0)
        bar_len = int(val / mx * 10) if mx > 0 else 0
        bar = '#' * bar_len + '-' * (10 - bar_len)
        lines.append(f"    {label:<22} {bar} {val}/{mx}")

    if qs['recommendations']:
        lines.append(f"  Recommendations:")
        for r in qs['recommendations']:
            lines.append(f"    • {r}")

    return "\n".join(lines)
