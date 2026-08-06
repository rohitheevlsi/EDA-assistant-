"""
FastAPI backend for the Live Verilog IDE.
Wraps the existing src/ pipeline behind a debounced HTTP endpoint and serves the IDE HTML.

Run: uvicorn api_server:app --port 8000 --reload
"""

import os
import sys
import json
import tempfile
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))

from src.toolchain import setup_toolchain_env
os.environ.update(setup_toolchain_env())

from src.parser_ir import parse_verilog, summarize_ast
from src.linter import lint_ast, run_verilator_lint
from src.synthesis import run_synthesis
from src.power_timing import estimate_power_timing_area
from src.complexity import compute_complexity

app = FastAPI(title="EDA Assistant Live IDE API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATE_PATH = Path(__file__).parent / "src" / "templates" / "ide.html"


class VerilogPayload(BaseModel):
    code: str


@app.get("/ide", response_class=HTMLResponse)
async def serve_ide():
    """Serve the Live Verilog IDE single-page application."""
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="IDE template not found.")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


@app.post("/analyze")
async def analyze_verilog(payload: VerilogPayload):
    """
    Analyze a Verilog snippet from the IDE editor.
    Returns lint warnings, KPIs, netlist JSON, and power/timing estimates.
    """
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Empty Verilog code.")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".v", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    result = {
        "lint_warnings": [],
        "verilator_warnings": "",
        "kpis": {},
        "netlist_json": None,
        "power_timing": {},
        "complexity": {},
        "error": None,
    }

    try:
        # --- Parse ---
        ast = parse_verilog(tmp_path)
        ir = summarize_ast(ast)
        ir_mod = ir["modules"][0] if ir["modules"] else {}

        # --- Lint ---
        result["lint_warnings"] = lint_ast(ast)
        result["verilator_warnings"] = run_verilator_lint(tmp_path)

        # --- Synthesis (includes write_json netlist) ---
        synth = run_synthesis(tmp_path)
        result["kpis"] = {
            "total_cells": synth.total_cells,
            "wires": synth.wires,
            "wire_bits": synth.wire_bits,
            "gates": synth.gates,
        }
        result["netlist_json"] = synth.netlist_json  # from write_json

        # --- Power / Timing ---
        pt = estimate_power_timing_area(synth)
        # Remove disclaimer from API payload (front-end shows it statically)
        pt.pop("disclaimer", None)
        result["power_timing"] = pt

        # --- Complexity ---
        result["complexity"] = compute_complexity(ast, ir_mod)

    except Exception as exc:
        result["error"] = traceback.format_exc()

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return JSONResponse(content=result)


@app.get("/health")
async def health():
    return {"status": "ok"}
