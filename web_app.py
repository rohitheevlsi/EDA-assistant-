"""
EDA Assistant — Web UI (Redesigned with VLSI Intelligence)
PCB copper-trace industrial aesthetic.
Run: streamlit run web_app.py
"""

import os
import sys
import json
import tempfile
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
from src.toolchain import setup_toolchain_env
os.environ.update(setup_toolchain_env())

from eda_assistant import analyze

# Page configuration
st.set_page_config(
    page_title="EDA Assistant · RTL Intelligence Platform",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (Copper/Emerald PCB Dark Mode Theme)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #060a08;
    color: #c0d0c5;
}

/* dot-grid background */
.main > .block-container {
    background-image: radial-gradient(circle, #102016 1px, transparent 1px);
    background-size: 24px 24px;
    background-color: #060a08;
    padding: 1.5rem 2rem 3rem;
    max-width: 1450px;
}

/* sidebar */
section[data-testid="stSidebar"] {
    background: #0a0f0d;
    border-right: 1px solid #14241c;
}
section[data-testid="stSidebar"] .block-container { padding: 1.5rem 1rem; }

/* topbar brand */
.brand-bar {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 1rem 0;
    border-bottom: 1px solid #14241c;
    margin-bottom: 1.5rem;
}
.brand-hex {
    width: 40px; height: 40px;
    background: #14b8a6;
    clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; color: #060a08; font-weight: 700;
}
.brand-title { font-size: 1.35rem; font-weight: 700; color: #eaf3ee; letter-spacing: -0.5px; }
.brand-sub   { font-size: 0.72rem; color: #4d7c66; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 2px; }
.brand-badge {
    margin-left: auto;
    background: #0b221a;
    border: 1px solid #14b8a6;
    color: #14b8a6;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 0.65rem;
    font-family: 'JetBrains Mono', monospace;
}

/* Module Chip Header */
.module-chip {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    background: #0b1410;
    border: 1px solid #1a3025;
    border-left: 4px solid #14b8a6;
    padding: 12px 20px;
    border-radius: 8px;
    margin-bottom: 1.2rem;
}
.module-chip .label { font-size: 0.68rem; color: #4d7c66; text-transform: uppercase; letter-spacing: 0.08em; }
.module-chip .name  { font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; color: #8fd4b2; font-weight: 600; }

/* KPI Cards */
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 1.5rem; }
.kpi {
    background: #0b1410;
    border: 1px solid #1a3025;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    position: relative;
    overflow: hidden;
}
.kpi::after {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #14b8a6, transparent);
}
.kpi .k-val  { font-family: 'JetBrains Mono', monospace; font-size: 1.8rem; font-weight: 600; color: #14b8a6; line-height: 1.1; }
.kpi .k-lbl  { font-size: 0.68rem; color: #4d7c66; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 5px; }
.kpi .k-icon { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); font-size: 1.5rem; opacity: 0.1; }
.kpi.green .k-val { color: #10b981; }
.kpi.green::after { background: linear-gradient(90deg, #10b981, transparent); }
.kpi.red .k-val   { color: #ef4444; }
.kpi.red::after   { background: linear-gradient(90deg, #ef4444, transparent); }
.kpi.orange .k-val { color: #f59e0b; }
.kpi.orange::after { background: linear-gradient(90deg, #f59e0b, transparent); }
.kpi.blue .k-val  { color: #3b82f6; }
.kpi.blue::after  { background: linear-gradient(90deg, #3b82f6, transparent); }

/* Section Label */
.sec-label {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.7rem; font-weight: 600;
    color: #4d7c66; text-transform: uppercase; letter-spacing: 0.12em;
    margin: 1.4rem 0 0.8rem;
}
.sec-label::after { content: ''; flex: 1; height: 1px; background: #1a3025; }

/* Lint Items */
.lint-item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    line-height: 1.4;
}
.lint-item.warn  { background: #1f190e; border: 1px solid #4a3614; color: #eab308; }
.lint-item.error { background: #201010; border: 1px solid #4d1818; color: #f87171; }
.lint-item.ok    { background: #081d13; border: 1px solid #144d2d; color: #10b981; }
.lint-item .badge {
    font-size: 0.6rem; padding: 1px 6px; border-radius: 3px;
    white-space: nowrap; font-weight: 700; flex-shrink: 0; margin-top: 1px;
}
.lint-item.warn  .badge { background: #4a3614; color: #eab308; }
.lint-item.error .badge { background: #4d1818; color: #f87171; }
.lint-item.ok    .badge { background: #144d2d; color: #10b981; }

/* Custom Progress Bars */
.progress-container { margin-bottom: 10px; }
.progress-label-row { display: flex; justify-content: space-between; font-size: 0.72rem; color: #8ea499; margin-bottom: 3px; }
.progress-bar-bg { background: #111d17; border-radius: 4px; height: 8px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, #10b981, #14b8a6); border-radius: 4px; }

/* Sidebar headings */
.sidebar-section {
    font-size: 0.65rem; font-weight: 700; color: #32503f;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin: 1.2rem 0 0.5rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid #1a3025;
}

/* Quality Card styling */
.quality-card {
    background: #0b1410;
    border: 1px solid #1a3025;
    border-radius: 10px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.grade-badge {
    font-size: 2.8rem;
    font-weight: 800;
    line-height: 1;
    color: #14b8a6;
    font-family: 'JetBrains Mono', monospace;
    text-align: center;
    background: #11261e;
    border-radius: 8px;
    padding: 10px;
    border: 1px solid #1d4032;
    display: inline-block;
    min-width: 80px;
}
.rec-bullet {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    margin-bottom: 8px;
    font-size: 0.82rem;
    color: #a3bcae;
}
.rec-bullet::before {
    content: '▶';
    font-size: 0.6rem;
    color: #14b8a6;
    margin-top: 3px;
}

/* Code blocks style */
.stCodeBlock { border: 1px solid #1a3025 !important; border-radius: 6px !important; }

/* Streamlit Tabs Override */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px; background: #070c0a;
    border-bottom: 1px solid #1a3025;
    padding: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border: none; border-radius: 0;
    padding: 8px 16px; font-size: 0.8rem; color: #4d7c66;
    font-family: 'JetBrains Mono', monospace;
    border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] {
    background: transparent; color: #14b8a6;
    border-bottom: 2px solid #14b8a6;
}
</style>
""", unsafe_allow_html=True)


# ── Brand Header ──────────────────────────────────────────────────────────
st.markdown("""
<div class="brand-bar">
  <div class="brand-hex">⬡</div>
  <div>
    <div class="brand-title">EDA Assistant</div>
    <div class="brand-sub">VLSI Design Intelligence Platform</div>
  </div>
  <div class="brand-badge">v2.0 · VLSI EXPERT</div>
</div>
""", unsafe_allow_html=True)


# ── Sidebar Configuration ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-section">Analysis Mode</div>', unsafe_allow_html=True)
    mode = st.radio("", ["Single Design Analysis", "Design Comparison"], label_visibility="collapsed")

    st.markdown('<div class="sidebar-section">Pipeline Stages</div>', unsafe_allow_html=True)
    use_llm = st.toggle("🧠 Gemini Explanation", value=True)
    use_synth = st.toggle("⚙️ Yosys Synthesis", value=True)
    use_tb = st.toggle("🧪 Testbench & Sim", value=True)

    st.markdown('<div class="sidebar-section">Source Input</div>', unsafe_allow_html=True)
    input_mode = st.radio("", ["Upload file", "Select sample"], label_visibility="collapsed")

    sample_files = [
        "alu_8bit.v",
        "uart_tx.v",
        "spi_master.v",
        "counter_gray.v",
        "priority_encoder.v",
        "clock_divider.v",
        "shift_register.v",
        "cdc_violation.v",
        "blocking_seq_bug.v",
        "width_mismatch_bug.v",
        "adder.v",
        "clean_fsm.v",
        "fifo.v",
        "latch_bug.v",
        "multidriven_bug.v"
    ]

    selected_sample = None
    if input_mode == "Select sample":
        selected_sample = st.selectbox("Sample Verilog file", sample_files, label_visibility="collapsed")

    st.markdown('<div class="sidebar-section">About Engine</div>', unsafe_allow_html=True)
    st.markdown("""
<div style='font-size:0.7rem;color:#4d7c66;line-height:1.6'>
<b>Lint:</b> Custom AST + Verilator<br>
<b>Complexity:</b> Cyclomatic / registers<br>
<b>Power/Timing:</b> 45nm standard cell mapping<br>
<b>Synthesis:</b> Technology-independent Yosys<br>
<b>Quality:</b> 6-factor weighted grading
</div>""", unsafe_allow_html=True)


# ── Load Verilog Source and Run Pipeline ──────────────────────────────────
uploaded_file = None
if input_mode == "Upload file":
    uploaded_file = st.file_uploader("Drop a Verilog file (.v / .sv)", type=["v", "sv"])

# Button to run analysis
run_analysis = st.button("🚀 Run Analysis Pipeline", use_container_width=True)

# Save or load files based on inputs
fp = None
is_temp = False
if input_mode == "Select sample" and selected_sample:
    fp = os.path.join("tests", "verilog", selected_sample)
elif input_mode == "Upload file" and uploaded_file:
    with tempfile.NamedTemporaryFile(suffix=".v", delete=False, mode="wb") as tmp:
        tmp.write(uploaded_file.getbuffer())
        fp = tmp.name
        is_temp = True

if not fp:
    st.markdown("""
    <div style='background:#0b1410;border:1px solid #1a3025;border-radius:10px;padding:3rem;text-align:center;margin-top:1.5rem'>
      <div style='font-size:3rem;margin-bottom:1rem;color:#14b8a6'>⬡</div>
      <h3 style='color:#eaf3ee;margin-bottom:0.5rem'>Select a Verilog file to analyze</h3>
      <p style='color:#6d8c7c;font-size:0.85rem;max-width:500px;margin:0 auto;'>
        Use the sidebar to choose a sample design (e.g., alu_8bit.v, uart_tx.v, or cdc_violation.v) or upload your own synthesizable Verilog module.
      </p>
    </div>""", unsafe_allow_html=True)
    st.stop()


# ── Run Analysis ───────────────────────────────────────────────────────────
if 'reports_cache' not in st.session_state:
    st.session_state['reports_cache'] = {}

report = None
if run_analysis or fp not in st.session_state['reports_cache']:
    with st.spinner("Processing through VLSI intelligence pipeline..."):
        try:
            report = analyze(fp, use_llm=use_llm, use_synth=use_synth, use_tb=use_tb)
            st.session_state['reports_cache'][fp] = report
        except Exception as e:
            st.error(f"Pipeline Execution Failed: {e}")
            st.stop()
        finally:
            if is_temp and fp and os.path.exists(fp):
                try:
                    os.unlink(fp)
                except Exception:
                    pass
else:
    report = st.session_state['reports_cache'][fp]


# ══════════════════════════════════════════════════════════════════════════════
# COMPARISON MODE
# ══════════════════════════════════════════════════════════════════════════════
if mode == "Design Comparison":
    st.subheader("⚖️ RTL Design Comparison & Delta Analysis")
    
    # Select another design to compare against
    comparison_target = st.selectbox("Select Target Design to Compare against baseline", sample_files, index=1)
    target_fp = os.path.join("tests", "verilog", comparison_target)
    
    # Run pipeline for target if not cached
    if target_fp not in st.session_state['reports_cache']:
        with st.spinner(f"Processing comparison target: {comparison_target}..."):
            try:
                target_report = analyze(target_fp, use_llm=use_llm, use_synth=use_synth, use_tb=use_tb)
                st.session_state['reports_cache'][target_fp] = target_report
            except Exception as e:
                st.error(f"Failed to analyze target: {e}")
                st.stop()
    else:
        target_report = st.session_state['reports_cache'][target_fp]

    # Render Side-by-Side Comparison
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"### Baseline: `{report.module_name}`")
        st.markdown(f"<div class='grade-badge'>{report.quality_score.get('grade','F')}</div>", unsafe_allow_html=True)
        st.write(f"Quality Score: **{report.quality_score.get('total_score',0)}/100**")
    
    with col2:
        st.markdown(f"### Target: `{target_report.module_name}`")
        st.markdown(f"<div class='grade-badge' style='color:#3b82f6; background:#11202e; border-color:#1e3752;'>{target_report.quality_score.get('grade','F')}</div>", unsafe_allow_html=True)
        st.write(f"Quality Score: **{target_report.quality_score.get('total_score',0)}/100**")

    st.markdown('<div class="sec-label">Metrics Delta Comparison</div>', unsafe_allow_html=True)
    
    # Build comparison dataframe
    data = []
    
    # Helper to get value
    def get_val(rep, key, subkey=None):
        if not rep: return 0
        if subkey:
            return rep.to_dict().get(key, {}).get(subkey, 0) if rep.to_dict().get(key) else 0
        return rep.to_dict().get(key, 0)
        
    metrics_to_compare = [
        ("Quality Score", "quality_score", "total_score", ""),
        ("Lint Issues", "lint_warnings", None, "count"),
        ("Cyclomatic Complexity", "complexity_metrics", "cyclomatic_complexity", ""),
        ("Total Logic Cells", "synthesis", "total_cells", ""),
        ("Total Registers (bits)", "complexity_metrics", "register_bits", ""),
        ("Estimated Area (um²)", "power_timing", "total_area_um2", ""),
        ("Total Power (uW)", "power_timing", "total_power_uw", ""),
        ("Critical Path (ps)", "power_timing", "critical_path_ps", "")
    ]
    
    for label, key, subkey, op in metrics_to_compare:
        if op == "count":
            val_base = len(getattr(report, key, []))
            val_targ = len(getattr(target_report, key, []))
        else:
            val_base = get_val(report, key, subkey)
            val_targ = get_val(target_report, key, subkey)
            
        diff = val_targ - val_base
        if isinstance(diff, float):
            diff_str = f"{diff:+.2f}"
        else:
            diff_str = f"{diff:+d}"
            
        data.append({
            "Metric": label,
            "Baseline Value": val_base,
            "Target Value": val_targ,
            "Delta": diff_str
        })
        
    df = pd.DataFrame(data)
    st.table(df)

    st.markdown('<div class="sec-label">Side-by-Side Code Comparison</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"Baseline Source: {os.path.basename(report.filepath)}")
        st.code(report.source_code, language="verilog")
    with c2:
        st.caption(f"Target Source: {os.path.basename(target_report.filepath)}")
        st.code(target_report.source_code, language="verilog")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE DESIGN ANALYSIS MODE
# ══════════════════════════════════════════════════════════════════════════════

# ── Module chip info ──────────────────────────────────────────────────────
ports_count = len(report.ir_summary.get("ports", []))
always_count = report.ir_summary.get("always_blocks", 0)

st.markdown(f"""
<div class="module-chip">
  <div>
    <div class="label">Analyzed Module</div>
    <div class="name">{report.module_name}</div>
  </div>
  <div style='margin-left:2rem'>
    <div class="label">Ports</div>
    <div style='font-family:JetBrains Mono,monospace;font-size:0.9rem;color:#eaf3ee'>{ports_count}</div>
  </div>
  <div style='margin-left:2rem'>
    <div class="label">Always Blocks</div>
    <div style='font-family:JetBrains Mono,monospace;font-size:0.9rem;color:#eaf3ee'>{always_count}</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── KPI Cards ─────────────────────────────────────────────────────────────
lint_n = len(report.lint_warnings)
lint_cls = "green" if lint_n == 0 else "red" if lint_n > 3 else "orange"

qs = report.quality_score
qs_val = qs.get("total_score", 0)
qs_grade = qs.get("grade", "F")
qs_cls = "green" if qs_val >= 85 else "orange" if qs_val >= 60 else "red"

cells_n = report.synthesis.total_cells if (report.synthesis and not report.synthesis.error) else "—"

pt = report.power_timing
crit_path = f"{pt.get('critical_path_ps', 0)} ps" if 'critical_path_ps' in pt else "—"

st.markdown(f"""
<div class="kpi-row">
  <div class="kpi {lint_cls}">
    <div class="k-val">{lint_n}</div>
    <div class="k-lbl">Lint Warnings</div>
    <div class="k-icon">⚠</div>
  </div>
  <div class="kpi {qs_cls}">
    <div class="k-val">{qs_grade} <span style='font-size:1.1rem;color:#8ea499'>({qs_val}/100)</span></div>
    <div class="k-lbl">RTL Quality Grade</div>
    <div class="k-icon">✓</div>
  </div>
  <div class="kpi">
    <div class="k-val">{cells_n}</div>
    <div class="k-lbl">Total Synthesis Cells</div>
    <div class="k-icon">⬡</div>
  </div>
  <div class="kpi blue">
    <div class="k-val">{crit_path}</div>
    <div class="k-lbl">Critical Path Delay</div>
    <div class="k-icon">⚡</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Tabs Configuration ─────────────────────────────────────────────────────
t_code, t_quality, t_metrics, t_power, t_synth, t_tb, t_raw = st.tabs([
    "⚡ Lint & Code",
    "📋 RTL Quality",
    "📊 Design Metrics",
    "🔌 Power & Timing",
    "⬡ Synthesis",
    "🧪 Testbench & Sim",
    "📄 Raw Report"
])


# ── TAB 1: LINT & CODE ─────────────────────────────────────────────────────
with t_code:
    st.markdown('<div class="sec-label">Source Code Viewer</div>', unsafe_allow_html=True)
    st.code(report.source_code, language="verilog")

    st.markdown('<div class="sec-label">Custom Lint Issues</div>', unsafe_allow_html=True)
    if report.lint_warnings:
        for w in report.lint_warnings:
            badge = "CDC" if "CDC" in w else "BLOCKING" if "BLOCKING" in w else "NON-BLOCKING" if "NONBLOCKING" in w else "LATCH" if "LATCH" in w else "WARN"
            cls = "error" if "CDC" in w or "MULTI" in w else "warn"
            st.markdown(f'<div class="lint-item {cls}"><span class="badge">{badge}</span>{w}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="lint-item ok"><span class="badge">CLEAN</span>No custom lint warnings detected. Ready for synthesis.</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-label">Verilator Lint Output</div>', unsafe_allow_html=True)
    vlines = [l.strip() for l in report.verilator_warnings.splitlines() if "%Warning" in l or "%Error" in l]
    if vlines:
        for l in vlines:
            cls = "error" if "%Error" in l else "warn"
            badge = "ERROR" if "%Error" in l else "WARNING"
            st.markdown(f'<div class="lint-item {cls}"><span class="badge">{badge}</span>{l}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="lint-item ok"><span class="badge">CLEAN</span>Verilator Linter: 0 warnings, 0 errors.</div>', unsafe_allow_html=True)


# ── TAB 2: RTL QUALITY ─────────────────────────────────────────────────────
with t_quality:
    st.markdown('<div class="sec-label">Quality Score breakdown</div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"""
        <div class="quality-card" style="text-align:center;">
          <div class="label" style="margin-bottom:10px;">RTL Letter Grade</div>
          <div class="grade-badge">{qs_grade}</div>
          <div style="font-size:1.1rem;font-weight:600;color:#eaf3ee;margin-top:15px;">{qs_val} / 100</div>
          <div style="font-size:0.75rem;color:#4d7c66;margin-top:5px;">RTL Code Quality Index</div>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown("<div class='quality-card'>", unsafe_allow_html=True)
        factors = [
            ("Lint Cleanliness", "lint_cleanliness", 25),
            ("Coding Style", "coding_style", 20),
            ("Design Structure", "design_structure", 20),
            ("Testability", "testability", 15),
            ("Complexity Balance", "complexity_balance", 10),
            ("Documentation", "documentation", 10)
        ]
        
        for label, key, max_pts in factors:
            val = qs.get("breakdown", {}).get(key, 0)
            pct = int((val / max_pts) * 100) if max_pts > 0 else 0
            st.markdown(f"""
            <div class="progress-container">
              <div class="progress-label-row">
                <span>{label}</span>
                <span>{val} / {max_pts} ({pct}%)</span>
              </div>
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: {pct}%"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="sec-label">VLSI Recommendations & Optimization Path</div>', unsafe_allow_html=True)
    if qs.get("recommendations"):
        for rec in qs["recommendations"]:
            st.markdown(f'<div class="rec-bullet">{rec}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="lint-item ok"><span class="badge">OPTIMIZED</span>Golden RTL: No recommendations needed! Code quality is excellent.</div>', unsafe_allow_html=True)

    # Gemini explanation text box
    st.markdown('<div class="sec-label">RTL Architecture Explanation (Gemini)</div>', unsafe_allow_html=True)
    if report.llm_explanation and "(LLM skipped)" not in report.llm_explanation:
        import html
        st.markdown(f"""
        <div style="background:#0b1410;border:1px solid #1a3025;border-radius:8px;padding:1.5rem;font-size:0.9rem;line-height:1.75;color:#c0d0c5;">
          {html.escape(report.llm_explanation)}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.write("LLM Analysis Skipped or not available.")


# ── TAB 3: DESIGN METRICS ──────────────────────────────────────────────────
with t_metrics:
    st.markdown('<div class="sec-label">Structural Complexity Analytics</div>', unsafe_allow_html=True)
    
    metrics = report.complexity_metrics
    if metrics:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="quality-card">
              <div class="label">Approximated Cyclomatic Complexity</div>
              <div style="font-size:2.5rem;font-weight:700;color:#14b8a6;margin:10px 0;">{metrics.get('approximated_cyclomatic_complexity', metrics.get('cyclomatic_complexity', 0))}</div>
              <div style="font-size:0.75rem;color:#6d8c7c;">Approximated complexity (1 + if_count + case_branches). This is a structural heuristic, not the exact McCabe formula.</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="quality-card">
              <div class="label">Register Allocation</div>
              <div style="font-size:2.5rem;font-weight:700;color:#3b82f6;margin:10px 0;">{metrics.get('register_bits', 0)} bits</div>
              <div style="font-size:0.75rem;color:#6d8c7c;">Total Flip-Flop/Register storage capacity allocated within module wires and registers.</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown('<div class="sec-label">State Machine & Control Density</div>', unsafe_allow_html=True)
            df_metrics = pd.DataFrame({
                "Metric": ["Port Count", "Internal Signals", "If Statements", "Case Statements", "Nesting Depth", "FSM Parameters"],
                "Count": [
                    metrics.get('port_count', 0),
                    metrics.get('signal_count', 0),
                    metrics.get('if_statements', 0),
                    metrics.get('case_statements', 0),
                    metrics.get('max_nesting_depth', 0),
                    metrics.get('fsm_parameters', 0)
                ]
            })
            st.dataframe(df_metrics, hide_index=True, use_container_width=True)

            if metrics.get('clock_domain_count', 0) > 0:
                st.info(f"Clock Domains detected: {', '.join(metrics.get('clock_domains', []))}")
    else:
        st.write("Complexity metrics not computed.")


# ── TAB 4: POWER & TIMING ──────────────────────────────────────────────────
with t_power:
    st.markdown('<div class="sec-label">Power & Area Estimation (45nm Node)</div>', unsafe_allow_html=True)
    st.warning("⚠️ **Disclaimer:** These power, area, and frequency values are rough structural heuristics estimated from technology-independent cell mappings, not actual sign-off Static Timing Analysis (STA) or power extraction.")
    
    pt = report.power_timing
    if pt and 'error' not in pt:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="quality-card">
              <div class="label">Estimated Total Power</div>
              <div style="font-size:2.2rem;font-weight:700;color:#14b8a6;margin:8px 0;">{pt.get('total_power_uw', 0)} uW</div>
              <div style="font-size:0.75rem;color:#6d8c7c;line-height:1.4">
                Leakage: {pt.get('leakage_power_nw', 0)} nW<br>
                Dynamic: {pt.get('dynamic_power_uw', 0)} uW (estimated @100MHz clock)
              </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="quality-card">
              <div class="label">Silicon Footprint</div>
              <div style="font-size:2.2rem;font-weight:700;color:#eab308;margin:8px 0;">{pt.get('total_area_um2', 0)} um²</div>
              <div style="font-size:0.75rem;color:#6d8c7c;">Estimated standard cell active gate area on a standard 45nm CMOS cell library.</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="quality-card">
              <div class="label">Max Estimated Frequency</div>
              <div style="font-size:2.2rem;font-weight:700;color:#ef4444;margin:8px 0;">{pt.get('max_freq_mhz', 0)} MHz</div>
              <div style="font-size:0.75rem;color:#6d8c7c;line-height:1.4">
                Critical Path: {pt.get('critical_path_ps', 0)} ps<br>
                Estimated logical gates depth: {pt.get('estimated_stages', 0)} stages
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Categorized cell counts
            cat_data = pd.DataFrame({
                "Cell Category": list(pt.get("cell_categories", {}).keys()),
                "Count": list(pt.get("cell_categories", {}).values())
            })
            st.bar_chart(cat_data, x="Cell Category", y="Count")
    else:
        st.warning("Power and timing estimates not available. Ensure synthesis stage runs successfully.")


# ── TAB 5: SYNTHESIS ───────────────────────────────────────────────────────
with t_synth:
    if report.synthesis and not report.synthesis.error:
        s = report.synthesis
        st.markdown('<div class="sec-label">Generic Cell Mapping Breakdown</div>', unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("Total synthesized cells", s.total_cells)
            st.metric("Wires count", s.wires)
            st.metric("Wire bits", s.wire_bits)
        
        with c2:
            if s.gates:
                gate_df = pd.DataFrame({
                    "Gate Cell Type": list(s.gates.keys()),
                    "Count": list(s.gates.values())
                }).sort_values("Count", ascending=False)
                st.dataframe(gate_df, hide_index=True, use_container_width=True)
            else:
                st.write("No specific gate breakdown available.")
    else:
        st.error(f"Synthesis failed or skipped. Error: {report.synthesis.error if report.synthesis else 'Skipped'}")


# ── TAB 6: TESTBENCH & SIMULATION ──────────────────────────────────────────
with t_tb:
    if report.testbench_enhanced:
        st.markdown('<div class="sec-label">Testbench Verification Status</div>', unsafe_allow_html=True)
        if report.testbench_compiles:
            st.success("✓ Testbench compiled successfully with iverilog.")
        else:
            st.error("✗ Testbench compilation failed.")
            if report.testbench_compile_output:
                st.code(report.testbench_compile_output, language="text")

        st.markdown('<div class="sec-label">Generated Testbench Code</div>', unsafe_allow_html=True)
        st.code(report.testbench_enhanced, language="verilog")

        if report.testbench_compiles and report.testbench_simulation_output:
            st.markdown('<div class="sec-label">Simulation stdout Log (vvp)</div>', unsafe_allow_html=True)
            st.code(report.testbench_simulation_output, language="text")
    else:
        st.write("Testbench generation skipped or failed.")


# ── TAB 7: RAW REPORT & DOWNLOADS ─────────────────────────────────────────
with t_raw:
    st.markdown('<div class="sec-label">Full ASCII Engineering Report</div>', unsafe_allow_html=True)
    st.code(report.to_text(), language="text")

    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇ Download Report (.txt)",
        report.to_text(),
        file_name=f"{report.module_name}_report.txt",
        mime="text/plain",
        use_container_width=True
    )
    c2.download_button(
        "⬇ Download Report (.json)",
        json.dumps(report.to_dict(), indent=2),
        file_name=f"{report.module_name}_report.json",
        mime="application/json",
        use_container_width=True
    )
