# FluxCore EDA — AI-Powered RTL Intelligence & Verification Platform

> **Unified single-page EDA platform** for Verilog/SystemVerilog RTL analysis, gate-level synthesis, static linting, ML-driven bug detection, PPA estimation, and testbench simulation — all in one dark-mode browser interface.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.100%2B-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Yosys](https://img.shields.io/badge/Yosys-Synthesis-4a90d9?style=flat-square)](https://github.com/YosysHQ/yosys)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

## ✨ What It Does

Point it at any Verilog file and it will:

| Feature | Description |
|---------|-------------|
| 🔍 **AST Parsing** | Parse RTL into a structured IR (ports, signals, always-blocks) using PyVerilog |
| ⚡ **Static Linting** | 10-rule custom engine + Verilator `-Wall` for common RTL bugs |
| 🧠 **LLM Explanation** | Gemini AI generates plain-English architecture explanation + structural risk notes |
| ⬡ **Gate Synthesis** | Real Yosys synthesis with technology-independent gate counts, wire stats, cell-type breakdowns |
| 🤖 **ML Bug Risk** | RandomForest anomaly classifier scores bug probability from AST + synthesis features |
| 📊 **RTL Quality Score** | 0–100 score + A+–F letter grade across 6 dimensions with optimization recommendations |
| 🔌 **45nm PPA Estimation** | Standard cell area, leakage/dynamic power, critical path delay, and Fmax calculation |
| 🧪 **Testbench & Simulation** | Auto-generated Verilog testbench compiled and executed with `iverilog` / `vvp` |
| ⚖️ **Design Comparison** | Side-by-side delta table comparing two designs across 8 key VLSI metrics |
| 📄 **Report Export** | Full ASCII engineering summary — copy to clipboard or download as `.txt` |

---

## 🚀 Quick Start

### Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.9+ | Core runtime | [python.org](https://www.python.org) |
| OSS CAD Suite | Yosys · Iverilog · Verilator | [YosysHQ/oss-cad-suite-build](https://github.com/YosysHQ/oss-cad-suite-build) — extract to `E:\oss-cad-suite` |
| Gemini API Key | LLM explanations *(optional)* | Free at [aistudio.google.com](https://aistudio.google.com) |

> **Note:** OSS CAD Suite is configured for `E:\oss-cad-suite` by default. If installed elsewhere, update the `OSS_CAD_BIN` path in `src/toolchain.py`.

---

### Step 1 — Clone the project

```powershell
git clone https://github.com/rohitheevlsi/EDA-assistant-.git
cd "EDA-assistant-"
```

### Step 2 — Create virtual environment & install dependencies

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3 — Configure your Gemini API key *(optional)*

```powershell
Copy-Item .env.example .env
notepad .env
```

Set inside `.env`:
```
GEMINI_API_KEY="your-key-here"
```

Get a free key at [aistudio.google.com](https://aistudio.google.com) → **Get API key**.

### Step 4 — Verify toolchain dependencies

```powershell
python check_deps.py
```

Expected:
```
[PASS] Verilator found.
[PASS] Yosys found.
[PASS] Python module 'pyverilog' found.
```

### Step 5 — Launch the Web Platform

```powershell
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🖥️ Web Interface — FluxCore UI

The platform features a full **3-panel SPA** layout:

```
┌─────────────────────────────────────────────────────────────────────┐
│  ⬡ FluxCore EDA   [📂 Sample Design] [📁 Upload .v] [🧠][🧪] [🚀] │  ← Top Nav
├──────────────┬──────────────────────────────────────────────────────┤
│              │  Left Pane: Monaco RTL Editor                        │
│  Sidebar:    │  (SystemVerilog syntax highlighting, auto-debounce)  │
│  • RTL Editor│─────────────────────────────────────────────────────┤
│  • Gate Net. │  KPI Strip: Grade | Lint | Cells | Delay | Power | Area │
│  • ML Risk   ├──────────────────────────────────────────────────────┤
│  • PPA       │  Tabs: ⬡ Synthesis | ⚡ Lint | 📋 Quality | 🔌 PPA  │
│  • Sim       │        📊 Complexity | 🧪 Testbench | ⚖️ Compare    │
│  • Delta     │                                                       │
├──────────────┴──────────────────────────────────────────────────────┤
│  FastAPI v2.0 · Yosys 0.38 · Iverilog 12.0                         │  ← Footer
└─────────────────────────────────────────────────────────────────────┘
```

**Dashboard Tabs:**

| Tab | Content |
|-----|---------|
| ⬡ **Gate Synthesis** | Dynamic SVG bar chart of gate distribution + full netlist table |
| ⚡ **Lint & ML Risk** | RandomForest bug anomaly score + AST lint warnings + Verilator console |
| 📋 **RTL Quality** | 6-factor score breakdown with progress bars, recommendations, Gemini notes |
| 🔌 **45nm PPA** | Silicon area, total/leakage/dynamic power, critical path, Fmax |
| 📊 **Complexity** | McCabe cyclomatic complexity, register bits, structural signal table |
| 🧪 **Testbench & Sim** | Iverilog compile status, auto-generated testbench code, VVP stdout |
| ⚖️ **Comparison** | Delta table vs. any sample design across 8 VLSI metrics |
| 📄 **Report** | Full ASCII engineering summary with clipboard copy & `.txt` download |

---

## ⌨️ CLI Usage

```powershell
# Full analysis — all stages
python eda_assistant.py analyze tests/verilog/alu_8bit.v

# Skip LLM (faster, offline)
python eda_assistant.py analyze tests/verilog/clean_fsm.v --no-llm

# Skip Yosys synthesis
python eda_assistant.py analyze tests/verilog/adder.v --no-synth

# Skip testbench generation
python eda_assistant.py analyze tests/verilog/fifo.v --no-tb

# Output as JSON
python eda_assistant.py analyze tests/verilog/uart_tx.v --json

# Save report to file
python eda_assistant.py analyze tests/verilog/spi_master.v --save reports/spi_report.txt
```

**CLI flags:**

| Flag | Effect |
|------|--------|
| `--no-llm` | Skip Gemini LLM explanation (fast, offline) |
| `--no-synth` | Skip Yosys synthesis |
| `--no-tb` | Skip testbench generation |
| `--json` | Print JSON output instead of plain text |
| `--save <path>` | Save report to file |

---

## 📂 Project Structure

```
EDA-assistant-/
├── api_server.py              ← FastAPI backend — all endpoints (analyze, compare, samples)
├── eda_assistant.py           ← CLI entry point & core pipeline orchestrator
├── check_deps.py              ← Toolchain dependency checker
├── requirements.txt           ← Python package list
├── .env.example               ← API key template (copy to .env)
│
├── src/
│   ├── templates/
│   │   └── ide.html           ← FluxCore EDA frontend SPA (Tailwind CSS + Monaco Editor)
│   ├── parser_ir.py           ← PyVerilog AST → structured IR
│   ├── linter.py              ← 10-rule static linter + Verilator integration
│   ├── llm_engine.py          ← Gemini API with 5-model fallback chain
│   ├── synthesis.py           ← Yosys runner + stats parser
│   ├── tb_generator.py        ← Auto testbench generation + iverilog/vvp execution
│   ├── aggregator.py          ← EDAReport dataclass, quality scoring, PPA estimation
│   └── toolchain.py           ← OSS CAD Suite PATH configuration
│
├── data_generation/
│   ├── generate_dataset.py    ← Synthetic bug injection dataset generator
│   └── train_bug_classifier.py← RandomForest ML model training + feature extraction
│
├── models/
│   └── bug_classifier.pkl     ← Trained RandomForest anomaly classifier
│
└── tests/
    └── verilog/               ← 15 sample Verilog designs
        ├── alu_8bit.v         ← 8-bit ALU (clean, A+ grade)
        ├── uart_tx.v          ← UART transmitter (clean)
        ├── spi_master.v       ← SPI master controller (clean)
        ├── clean_fsm.v        ← 2-state FSM (clean — no false positives)
        ├── fifo.v             ← Synchronous FIFO (clean)
        ├── shift_register.v   ← Parameterized shift register (clean)
        ├── clock_divider.v    ← Clock divider circuit (clean)
        ├── counter_gray.v     ← Gray code counter (clean)
        ├── priority_encoder.v ← 8-to-3 priority encoder (clean)
        ├── adder.v            ← Parameterized adder (clean)
        ├── latch_bug.v        ← Inferred latch → triggers LATCH warning
        ├── multidriven_bug.v  ← Multi-driven net → triggers MULTI-DRIVEN warning
        ├── blocking_seq_bug.v ← Blocking in clocked block → BLOCKING-IN-SEQ
        ├── cdc_violation.v    ← No synchronizer → CDC-CROSSING warning
        └── width_mismatch_bug.v ← Port width mismatch → WIDTH-MISMATCH warning
```

---

## 🔍 Lint Rules

| Rule | What It Detects | VLSI Impact |
|------|----------------|-------------|
| **LATCH** | Combinational block without `else`/`default` | Inferred level-sensitive latch |
| **MULTI-DRIVEN** | Signal written in multiple `always` blocks | Bus contention & simulation mismatch |
| **CDC-CROSSING** | Signal crossing clock domains without synchronizer | Metastability & silicon failure |
| **BLOCKING-IN-SEQ** | Blocking `=` in clocked `always @(posedge)` | Simulation race condition |
| **NONBLOCKING-IN-COMB** | Non-blocking `<=` in combinational block | Synthesis/simulation mismatch |
| **UNDRIVEN-PORT** | Output port declared but never assigned | Floating pin |
| **UNUSED-SIGNAL** | Wire/reg never read or driven | Redundant logic |
| **NO-DEFAULT-CASE** | `case` without `default` in sequential block | Undefined FSM state |
| **WIDTH-MISMATCH** | Port/signal width inconsistency | Silent truncation bugs |
| **Verilator** | Full `-Wall` linting pass | Synthesizability check |

---

## 🤖 ML Bug Anomaly Classifier

A **RandomForest classifier** (`models/bug_classifier.pkl`) trained on synthetically injected RTL anti-patterns:

- **Features**: AST structure (always-block count, nesting depth, signal ratios) + Yosys synthesis metrics (gate count, flip-flop density, MUX ratio)
- **Output**: Bug probability score (0–100%) with LOW / MODERATE / HIGH RISK badge
- **Retrain** the model at any time:

```powershell
python data_generation/train_bug_classifier.py
```

---

## 🔌 API Endpoints

The FastAPI backend exposes these endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` or `/ide` | Serve the FluxCore EDA frontend SPA |
| `GET` | `/health` | Health check + model load status |
| `GET` | `/samples` | List available sample `.v` files |
| `GET` | `/sample/{filename}` | Fetch source code of a sample |
| `POST` | `/analyze` | Run full EDA pipeline on submitted Verilog code |
| `POST` | `/compare` | Side-by-side comparison of two Verilog modules |

**`POST /analyze` payload:**
```json
{
  "code": "module my_module(...); endmodule",
  "use_llm": false,
  "use_synth": true,
  "use_tb": true
}
```

---

## ⚙️ 45nm PPA Estimation Methodology

PPA values are **structural heuristics** mapped from Yosys technology-independent gate counts to a 45nm standard cell library model:

- **Area**: Per-cell footprint in μm² summed across the synthesized netlist
- **Leakage Power**: Static dissipation from standard cell lookup table
- **Dynamic Power**: `P = α · C · V² · f` modeled at 100 MHz, 10% toggle rate
- **Critical Path**: Maximum logic depth × standard cell propagation delay

> ⚠️ These are **rapid estimation heuristics** intended for early-stage design exploration. For silicon-accurate results, use a proper STA tool (OpenSTA, PrimeTime) with a characterized cell library.

---

## 🛠️ Open-Source Tools Used

| Tool | Role |
|------|------|
| [PyVerilog](https://github.com/PyHDI/Pyverilog) | Verilog AST parser |
| [Yosys](https://github.com/YosysHQ/yosys) | Open-source synthesis suite |
| [Verilator](https://github.com/verilator/verilator) | HDL linter + simulator |
| [Iverilog](https://github.com/steveicarus/iverilog) | Verilog compiler + VVP runtime |
| [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build) | Prebuilt Windows binaries |
| [FastAPI](https://fastapi.tiangolo.com/) | Backend web framework |
| [Google Gemini](https://ai.google.dev/) | LLM architecture analysis |
| [Monaco Editor](https://microsoft.github.io/monaco-editor/) | In-browser code editor (VS Code engine) |
| [scikit-learn](https://scikit-learn.org/) | RandomForest ML classifier |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built for VLSI/FPGA designers who need rapid RTL insight without heavyweight EDA tool setup.*
