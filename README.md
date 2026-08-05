# EDA Assistant — AI-Powered RTL Analysis Tool

An open-source, AI-driven assistant for chip designers. Point it at any Verilog file and it will:

- **Parse** the RTL into a structured IR (ports, signals, always-blocks)
- **Lint** for common RTL bugs: inferred latches, multi-driven nets, width mismatches (custom engine + Verilator)
- **Explain** what the module does in plain English, with qualitative power and timing risk notes (via Gemini)
- **Synthesize** with Yosys and report real gate counts, wire stats, and cell-type breakdowns
- **Generate a testbench** with stimulus and assertions, compiled and validated with `iverilog`
- **Display everything** in a Streamlit web dashboard with tabs, KPI cards, and download buttons

---

## Quick Start

### Prerequisites

| Tool | Purpose | Where to get it |
|------|---------|----------------|
| Python 3.9+ | Core runtime | [python.org](https://www.python.org) |
| OSS CAD Suite | Yosys, Verilator, iverilog | [github.com/YosysHQ/oss-cad-suite-build](https://github.com/YosysHQ/oss-cad-suite-build) — extract to `E:\oss-cad-suite` |
| Gemini API key | LLM explanations | Free at [aistudio.google.com](https://aistudio.google.com) |

> **Note:** The OSS CAD Suite path is hardcoded to `E:\oss-cad-suite`. If you extract elsewhere, update the `OSS_CAD_BIN` constant at the top of `eda_assistant.py` and `web_app.py`.

---

### Step 1 — Clone or download the project

```
cd "E:\SEM 3 ai chip"
```

### Step 2 — Create a virtual environment and install dependencies

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3 — Set your Gemini API key

Copy `.env.example` to `.env` and fill in your key:

```powershell
Copy-Item .env.example .env
notepad .env
```

Edit `.env` so it contains:

```
GEMINI_API_KEY="your-actual-key-here"
```

Get a free key at [aistudio.google.com](https://aistudio.google.com) → **Get API key**.

### Step 4 — Verify dependencies

```powershell
python check_deps.py
```

Expected output:
```
[PASS] Verilator found.
[PASS] Yosys found.
[PASS] Python module 'pyverilog' found.
```

---

## Running the CLI

```powershell
# Full analysis — all stages enabled
python eda_assistant.py analyze tests/verilog/latch_bug.v

# Skip LLM (faster, works offline)
python eda_assistant.py analyze tests/verilog/clean_fsm.v --no-llm

# Skip Yosys synthesis
python eda_assistant.py analyze tests/verilog/adder.v --no-synth

# Skip testbench generation
python eda_assistant.py analyze tests/verilog/fifo.v --no-tb

# Output as JSON
python eda_assistant.py analyze tests/verilog/clean_fsm.v --json

# Save report to a file
python eda_assistant.py analyze tests/verilog/adder.v --save reports/adder_report.txt
```

**CLI flags:**

| Flag | Effect |
|------|--------|
| `--no-llm` | Skip Gemini LLM explanation (fast, offline) |
| `--no-synth` | Skip Yosys synthesis |
| `--no-tb` | Skip testbench generation |
| `--json` | Print JSON instead of plain text |
| `--save <path>` | Save report to file |

---

## Running the Web Dashboard

```powershell
streamlit run web_app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

The dashboard lets you:
1. **Upload any `.v` file** or pick one of the 5 built-in samples from the sidebar
2. Toggle LLM, synthesis, and testbench generation on/off
3. Click **🚀 Run Analysis** to run the full pipeline
4. Browse results across five tabs: **Lint**, **LLM Analysis**, **Synthesis**, **Testbench**, **Raw Report**
5. Download the report as `.txt` or `.json`

---

## Project Structure

```
eda_assistant.py          ← CLI entry point
web_app.py                ← Streamlit web UI
check_deps.py             ← Dependency checker
requirements.txt          ← Python dependencies
.env.example              ← API key template (copy to .env)
src/
  parser_ir.py            ← Pyverilog AST → unified IR
  linter.py               ← Static rule checks + Verilator integration
  llm_engine.py           ← Gemini API with multi-model fallback chain
  synthesis.py            ← Yosys synthesis runner + stats parser
  tb_generator.py         ← Testbench skeleton + LLM-enhanced stimulus
  aggregator.py           ← EDAReport dataclass + text/JSON rendering
tests/
  verilog/
    adder.v               ← Parameterized adder (clean)
    clean_fsm.v           ← Two-block FSM (clean — no false positives)
    fifo.v                ← Synchronous FIFO (clean)
    latch_bug.v           ← Inferred latch bug (triggers LATCH warning)
    multidriven_bug.v     ← Multi-driven net bug (triggers MULTI-DRIVEN warning)
reports/                  ← Generated reports (git-ignored)
```

---

## Lint Rules

| Rule | What it detects | VLSI Impact |
|------|----------------|-------------|
| **LATCH** | Combinational block without `else`/`default` | Inferred level-sensitive latch |
| **MULTI-DRIVEN** | Same signal written in multiple blocks | Bus contention & simulation mismatches |
| **CDC-CROSSING** | Signals crossing clocks without synchronizers | Metastability & silicon failure |
| **BLOCKING-IN-SEQ** | Blocking assignments (`=`) in clocked blocks | Simulation race conditions |
| **NONBLOCKING-IN-COMB** | Non-blocking assignments (`<=`) in combo blocks | Simulation/synthesis mismatches |
| **UNDRIVEN-PORT** | Declared output port never assigned | Floating pins |
| **UNUSED-SIGNAL** | Declared wire/reg never read or driven | Redundant logic |
| **NO-DEFAULT-CASE** | `case` statement without default in sequential block | Undefined state machine behavior |
| **Verilator** | All standard Verilator `-Wall` warnings | Full synthesizability check |

---

## Power, Timing, and Area Estimation
A quantitative estimation engine maps synthesized Yosys cells to standard 45nm CMOS cell libraries:
- **Total Area**: Calculates silicon footprint based on physical cell areas.
- **Leakage Power**: Static dissipation calculated from gate lookup values.
- **Dynamic Power**: Dynamic load dissipation modeled at 100MHz clock and 10% toggle rate.
- **Critical Path Delay**: Estimates maximum logic depth and propagation delays.

---

## Design Complexity Metrics
Calculates core metrics for architectural reviews:
- **Cyclomatic Complexity**: Measures execution paths.
- **Register Storage**: Total flip-flop bits allocated.
- **Clock Domains**: Enumerates clock domains to flag crossing boundaries.
- **Complexity Score & Grade**: Rating of design scale (Simple to Highly Complex).

---

## RTL Quality Score & Grading
Computes a **0–100 score** and **A+ to F letter grade** based on Lint Cleanliness (including Verilator warnings), Coding Style, Design Structure, Testability, and Documentation. Provides detailed bulleted recommendations for silicon optimization.

---

## Design Comparison Mode
Compare baseline and target designs side-by-side:
- **Delta Table**: Visualizes comparison of gates, area, power, speed, complexity, and quality score.
- **Diff Code Viewer**: Inspects Verilog files side-by-side.

---

## Open-Source Tools Used

- [Pyverilog](https://github.com/PyHDI/Pyverilog) — Verilog parser
- [Yosys](https://github.com/YosysHQ/yosys) — Open synthesis suite
- [Verilator](https://github.com/verilator/verilator) — HDL linter/simulator
- [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build) — Windows binaries
- [Google Gemini](https://ai.google.dev/) — LLM reasoning layer
- [Streamlit](https://streamlit.io/) — Web dashboard

---

## License

MIT License
