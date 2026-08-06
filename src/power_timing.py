"""
Power / Timing / Area Estimation Engine
Uses Yosys synthesis output + structural IR to compute VLSI design estimates.
All estimates are grounded in cell-count data from Yosys — no LLM speculation.

If models/power_timing_model.pkl exists (produced by train_power_model.py),
ML predictions are used instead of the hand-written heuristics.
"""

import os as _os
import math as _math

_MODEL = None
_MODEL_META = None
_MODEL_PATH = _os.path.join(_os.path.dirname(__file__), '..', 'models', 'power_timing_model.pkl')
_META_PATH  = _os.path.join(_os.path.dirname(__file__), '..', 'models', 'model_meta.json')

try:
    import joblib as _joblib
    if _os.path.exists(_MODEL_PATH):
        _MODEL = _joblib.load(_MODEL_PATH)
        import json as _json
        if _os.path.exists(_META_PATH):
            with open(_META_PATH) as _f:
                _MODEL_META = _json.load(_f)
except Exception as _e:
    _MODEL = None

# Standard cell area/power lookup tables (approximate, technology-relative)
# Values are normalized to a generic 45nm process node
CELL_AREA_45NM = {
    # cell_type: area in um^2 (approximate)
    '$_NOT_': 0.532, '$_BUF_': 0.798,
    '$_AND_': 0.798, '$_NAND_': 0.798,
    '$_OR_': 0.798, '$_NOR_': 0.798,
    '$_XOR_': 1.596, '$_XNOR_': 1.596,
    '$_MUX_': 1.862, '$_NMUX_': 1.862,
    '$_AOI3_': 1.330, '$_OAI3_': 1.330,
    '$_AOI4_': 1.596, '$_OAI4_': 1.596,
    '$_DFF_P_': 3.990, '$_DFF_N_': 3.990,
    '$_DFF_PP0_': 4.788, '$_DFF_PP1_': 4.788,
    '$_DFF_PN0_': 4.788, '$_DFF_PN1_': 4.788,
    '$_DFFE_PP_': 5.054, '$_DFFE_PN_': 5.054,
    '$_SDFF_PP0_': 5.586, '$_SDFF_PP1_': 5.586,
    '$_DLATCH_P_': 3.192, '$_DLATCH_N_': 3.192,
}

# Leakage power per cell type in nW (approximate 45nm)
CELL_LEAKAGE_45NM = {
    '$_NOT_': 1.2, '$_BUF_': 1.8,
    '$_AND_': 2.1, '$_NAND_': 1.9,
    '$_OR_': 2.1, '$_NOR_': 1.9,
    '$_XOR_': 4.2, '$_XNOR_': 4.2,
    '$_MUX_': 5.0, '$_NMUX_': 5.0,
    '$_AOI3_': 3.5, '$_OAI3_': 3.5,
    '$_AOI4_': 4.0, '$_OAI4_': 4.0,
    '$_DFF_P_': 12.0, '$_DFF_N_': 12.0,
    '$_DFF_PP0_': 14.0, '$_DFF_PP1_': 14.0,
    '$_DFF_PN0_': 14.0, '$_DFF_PN1_': 14.0,
    '$_DFFE_PP_': 15.0, '$_DFFE_PN_': 15.0,
    '$_SDFF_PP0_': 16.0, '$_SDFF_PP1_': 16.0,
    '$_DLATCH_P_': 10.0, '$_DLATCH_N_': 10.0,
}

# Gate delay in ps (approximate 45nm typical corner)
CELL_DELAY_45NM = {
    '$_NOT_': 12, '$_BUF_': 18,
    '$_AND_': 25, '$_NAND_': 20,
    '$_OR_': 25, '$_NOR_': 20,
    '$_XOR_': 40, '$_XNOR_': 40,
    '$_MUX_': 35, '$_NMUX_': 35,
    '$_AOI3_': 30, '$_OAI3_': 30,
    '$_AOI4_': 35, '$_OAI4_': 35,
    '$_DFF_P_': 80, '$_DFF_N_': 80,
}

DEFAULT_AREA = 1.5     # um^2 for unknown cells
DEFAULT_LEAKAGE = 3.0  # nW for unknown cells
DEFAULT_DELAY = 30     # ps for unknown cells


def estimate_power_timing_area(synth_result, complexity_metrics=None):
    """
    Compute power, timing, and area estimates from Yosys synthesis results.

    When models/power_timing_model.pkl is present (run train_power_model.py to
    generate it), uses the trained ML model.  Falls back to hand-written 45nm
    heuristics when the model file is absent.

    Args:
        synth_result: SynthesisResult from synthesis.py
        complexity_metrics: dict from complexity.py (optional)

    Returns:
        dict with power/timing/area estimates
    """
    if not synth_result or synth_result.error:
        return {
            'error': synth_result.error if synth_result else 'No synthesis data',
            'total_area_um2': 0, 'leakage_power_nw': 0,
            'dynamic_power_uw': 0, 'critical_path_ps': 0,
            'max_freq_mhz': 0, 'cell_categories': {},
        }

    # ── ML Prediction Path ────────────────────────────────────────────────────
    if _MODEL is not None:
        cx = complexity_metrics or {}
        g  = synth_result.gates
        total = synth_result.total_cells or 0
        ff    = sum(n for c,n in g.items() if 'DFF' in c or 'DLATCH' in c or 'SDFF' in c)
        mux   = sum(n for c,n in g.items() if 'MUX' in c)
        buf   = sum(n for c,n in g.items() if 'BUF' in c or 'NOT' in c)
        logic = total - ff - mux - buf

        import pandas as _pd
        feat = _pd.DataFrame([{
            'total_cells':   total,
            'ff_cells':      ff,
            'logic_cells':   logic,
            'mux_cells':     mux,
            'buf_cells':     buf,
            'wires':         synth_result.wires,
            'wire_bits':     synth_result.wire_bits,
            'memory_bits':   synth_result.memory_bits,
            'register_bits': cx.get('register_bits', 0),
            'clock_domains': cx.get('clock_domain_count', 0),
            'approx_cc':     cx.get('approximated_cyclomatic_complexity', 1),
            'nesting_depth': cx.get('max_nesting_depth', 0),
            'port_count':    cx.get('port_count', 0),
            'always_blocks': cx.get('always_blocks', 0),
        }])
        try:
            pred = _MODEL.predict(feat)[0]   # [area, power, delay]
            area_ml, power_ml, delay_ml = float(pred[0]), float(pred[1]), float(pred[2])
            freq_ml = round(1e6 / max(delay_ml, 1), 1)
            n_train = (_MODEL_META or {}).get('n_train', '?')
            return {
                'total_area_um2':   round(area_ml, 2),
                'area_breakdown':   {},
                'leakage_power_nw': 0,
                'dynamic_power_uw': round(power_ml, 4),
                'total_power_uw':   round(power_ml, 4),
                'critical_path_ps': int(delay_ml),
                'estimated_stages': max(1, int(_math.log2(max(total - ff, 2)))),
                'max_freq_mhz':     freq_ml,
                'cell_categories': {
                    'Flip-Flops': ff, 'Logic Gates': logic,
                    'MUX': mux, 'Buffers/Inverters': buf,
                },
                'total_cells':   total,
                'combo_cells':   total - ff,
                'sequential_cells': ff,
                'disclaimer': f'ML-estimated (GradientBoosting model trained on {n_train} synthesized designs). Not sign-off STA.',
            }
        except Exception:
            pass   # fall through to heuristics

    gates = synth_result.gates


    # ── Area Estimation ──
    total_area = 0.0
    area_breakdown = {}
    for cell, count in gates.items():
        cell_area = CELL_AREA_45NM.get(cell, DEFAULT_AREA)
        area = cell_area * count
        total_area += area
        area_breakdown[cell] = round(area, 2)

    # ── Leakage Power ──
    total_leakage = 0.0
    for cell, count in gates.items():
        lk = CELL_LEAKAGE_45NM.get(cell, DEFAULT_LEAKAGE)
        total_leakage += lk * count

    # ── Dynamic Power Estimate ──
    # P_dynamic = alpha * C_load * V^2 * f
    # Simplified: use cell count as proxy, assume 10% toggle rate, 1.0V, 100MHz
    alpha = 0.1
    v_dd = 1.0
    f_mhz = 100
    cap_per_cell_ff = 2.0  # fF average load capacitance
    total_cells = synth_result.total_cells
    dynamic_power_uw = alpha * (cap_per_cell_ff * 1e-15) * (v_dd ** 2) * (f_mhz * 1e6) * total_cells * 1e6

    # ── Critical Path Estimation ──
    # Count combinational cells (non-FF) as approximate logic depth
    combo_cells = 0
    ff_cells = 0
    mux_cells = 0
    logic_cells = 0
    buf_cells = 0

    for cell, count in gates.items():
        if 'DFF' in cell or 'DLATCH' in cell or 'SDFF' in cell:
            ff_cells += count
        elif 'MUX' in cell:
            mux_cells += count
        elif 'BUF' in cell or 'NOT' in cell:
            buf_cells += count
        else:
            logic_cells += count
        if 'DFF' not in cell and 'DLATCH' not in cell and 'SDFF' not in cell:
            combo_cells += count

    # Rough critical path: assume sqrt(combo_cells) stages as average
    import math
    estimated_stages = max(1, int(math.sqrt(combo_cells)))
    avg_delay = sum(CELL_DELAY_45NM.get(c, DEFAULT_DELAY) for c in gates) / max(len(gates), 1)
    critical_path_ps = int(estimated_stages * avg_delay)

    # Max frequency
    max_freq_mhz = round(1e6 / max(critical_path_ps, 1), 1) if critical_path_ps > 0 else 0

    return {
        'total_area_um2': round(total_area, 2),
        'area_breakdown': area_breakdown,
        'leakage_power_nw': round(total_leakage, 2),
        'dynamic_power_uw': round(dynamic_power_uw, 4),
        'total_power_uw': round(total_leakage / 1000 + dynamic_power_uw, 4),
        'critical_path_ps': critical_path_ps,
        'estimated_stages': estimated_stages,
        'max_freq_mhz': max_freq_mhz,
        'cell_categories': {
            'Flip-Flops': ff_cells,
            'Logic Gates': logic_cells,
            'MUX': mux_cells,
            'Buffers/Inverters': buf_cells,
        },
        'total_cells': total_cells,
        'combo_cells': combo_cells,
        'sequential_cells': ff_cells,
        'disclaimer': 'These power, area, and frequency values are rough structural heuristics estimated from technology-independent cell mappings, not actual sign-off Static Timing Analysis (STA) or power extraction.',
    }


def format_power_timing_report(pt):
    if pt.get('error'):
        return f"  Error: {pt['error']}"
    lines = [
        f"  Total Area: {pt['total_area_um2']} um² (Heuristic 45nm estimate)",
        f"  Leakage Power: {pt['leakage_power_nw']} nW (Heuristic 45nm estimate)",
        f"  Dynamic Power: {pt['dynamic_power_uw']} uW (@100MHz, 10% toggle, 1.0V)",
        f"  Total Power: {pt['total_power_uw']} uW (Heuristic 45nm estimate)",
        f"  Critical Path: ~{pt['critical_path_ps']} ps ({pt['estimated_stages']} logic stages, Heuristic)",
        f"  Max Frequency: ~{pt['max_freq_mhz']} MHz (Heuristic)",
        f"  NOTE: {pt.get('disclaimer')}",
        f"  Cell Categories:",
    ]
    for cat, count in pt.get('cell_categories', {}).items():
        lines.append(f"    {cat:<25} {count}")
    return "\n".join(lines)
