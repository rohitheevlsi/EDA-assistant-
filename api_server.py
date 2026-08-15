"""
EDA Assistant — Unified Web Platform API Server
Serves the full single-page Verilog IDE & RTL Intelligence Dashboard.
Runs full linting, Yosys synthesis, PPA estimation, quality scoring, testbench generation, simulation, ML bug prediction, and design comparison.

Run: uvicorn api_server:app --port 8000 --reload
"""

import os
import sys
import json
import tempfile
import traceback
import pickle
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))

from src.toolchain import setup_toolchain_env
os.environ.update(setup_toolchain_env())

from eda_assistant import analyze as run_eda_analysis
from data_generation.train_bug_classifier import extract_ml_features

app = FastAPI(title="EDA Assistant — Unified RTL Intelligence Platform", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATE_PATH = Path(__file__).parent / "src" / "templates" / "ide.html"
SAMPLES_DIR = Path(__file__).parent / "tests" / "verilog"

# Load ML Bug Classifier if available
MODEL_PATH = Path(__file__).parent / "models" / "bug_classifier.pkl"
bug_model = None
if MODEL_PATH.exists():
    try:
        with open(MODEL_PATH, "rb") as f:
            bug_model = pickle.load(f)
    except Exception as e:
        print(f"[Warning] Failed to load bug_classifier.pkl: {e}")


class VerilogPayload(BaseModel):
    code: str
    use_llm: bool = True
    use_synth: bool = True
    use_tb: bool = True


class ComparePayload(BaseModel):
    base_code: str
    target_code: str
    use_llm: bool = False
    use_synth: bool = True
    use_tb: bool = True


@app.get("/", response_class=HTMLResponse)
@app.get("/ide", response_class=HTMLResponse)
async def serve_ide():
    """Serve the Unified EDA Assistant IDE & Dashboard web application."""
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="IDE template not found.")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


@app.get("/samples")
async def list_samples():
    """List available sample Verilog files."""
    if not SAMPLES_DIR.exists():
        return {"samples": []}
    files = sorted([f.name for f in SAMPLES_DIR.glob("*.v")])
    return {"samples": files}


@app.get("/sample/{filename}")
async def get_sample(filename: str):
    """Fetch source code for a specific sample file."""
    file_path = SAMPLES_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Sample file not found.")
    return {"filename": filename, "code": file_path.read_text(encoding="utf-8")}


def _compute_bug_prob(report) -> Optional[float]:
    """Calculate ML bug probability from synthesis and AST features."""
    if not bug_model or not report.synthesis:
        return None
    try:
        from pyverilog.vparser.parser import parse
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False, encoding="utf-8") as tmp:
            tmp.write(report.source_code)
            tmp_path = tmp.name
        try:
            ast, _ = parse([tmp_path])
        finally:
            os.unlink(tmp_path)

        feat = extract_ml_features(ast, report.synthesis, report.complexity_metrics)
        import pandas as pd
        df = pd.DataFrame([feat])
        prob = bug_model.predict_proba(df)[0][1]
        return round(float(prob) * 100, 1)
    except Exception as e:
        print(f"[Warning] Bug prediction error: {e}")
        return None


@app.post("/analyze")
async def analyze_verilog(payload: VerilogPayload):
    """
    Comprehensive EDA analysis endpoint.
    Runs lint, complexity, synthesis, PPA estimation, quality score, testbench, and ML bug classifier.
    """
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Empty Verilog code.")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False, encoding="utf-8") as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        report = run_eda_analysis(
            tmp_path,
            use_llm=payload.use_llm,
            use_synth=payload.use_synth,
            use_tb=payload.use_tb,
        )
        res = report.to_dict()
        res["report_text"] = report.to_text()
        res["bug_probability"] = _compute_bug_prob(report)
        res["error"] = None
        return JSONResponse(content=res)
    except Exception as exc:
        return JSONResponse(
            status_code=200,
            content={"error": traceback.format_exc(), "module_name": "unknown"},
        )
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.post("/compare")
async def compare_verilog(payload: ComparePayload):
    """
    Side-by-side design comparison endpoint.
    Calculates delta metrics between baseline and target designs.
    """
    if not payload.base_code.strip() or not payload.target_code.strip():
        raise HTTPException(status_code=400, detail="Both baseline and target Verilog code required.")

    def run_one(code_str):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False, encoding="utf-8") as tmp:
            tmp.write(code_str)
            p = tmp.name
        try:
            rep = run_eda_analysis(p, use_llm=False, use_synth=True, use_tb=False)
            d = rep.to_dict()
            d["bug_probability"] = _compute_bug_prob(rep)
            return d
        finally:
            try:
                os.unlink(p)
            except Exception:
                pass

    try:
        base_res = run_one(payload.base_code)
        target_res = run_one(payload.target_code)
        return JSONResponse(content={"base": base_res, "target": target_res})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok", "bug_model_loaded": bug_model is not None}
