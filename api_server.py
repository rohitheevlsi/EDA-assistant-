"""
FastAPI Server for EDA Assistant.
Consolidates all backend services: AST parsing, Verilator/Custom Linting,
Yosys Synthesis, PPA Estimation, ML Bug Probability, Testbench Generation, and Comparison.
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup toolchain binaries (Yosys, Iverilog, Verilator)
from src.toolchain import setup_toolchain_env
os.environ.update(setup_toolchain_env())

from eda_assistant import analyze as run_eda_analysis
from data_generation.train_bug_classifier import extract_ml_features

app = FastAPI(title="EDA Assistant — Unified RTL Intelligence Platform", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static templates directory
TEMPLATES_DIR = PROJECT_ROOT / "src" / "templates"
SAMPLES_DIR = PROJECT_ROOT / "tests" / "verilog"

# Attempt to load ML Bug Classifier model
MODEL_PATH = PROJECT_ROOT / "models" / "bug_classifier.pkl"
bug_model = None
if MODEL_PATH.exists():
    try:
        import joblib
        bug_model = joblib.load(MODEL_PATH)
        print("[Info] ML Bug Classifier model loaded successfully.")
    except Exception as err:
        print(f"[Warning] Failed to load ML Bug Classifier model: {err}")


class VerilogPayload(BaseModel):
    code: str
    use_llm: bool = False
    use_synth: bool = True
    use_tb: bool = True


class ComparisonPayload(BaseModel):
    base_code: str
    target_code: str


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "bug_model_loaded": bug_model is not None}


@app.get("/", response_class=HTMLResponse)
@app.get("/ide", response_class=HTMLResponse)
async def get_ide_page():
    """Serve the unified Single Page Application interface."""
    ide_html_path = TEMPLATES_DIR / "ide.html"
    if not ide_html_path.exists():
        raise HTTPException(status_code=404, detail="IDE template missing.")
    return HTMLResponse(content=ide_html_path.read_text(encoding="utf-8"))


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
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

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
    Runs lint, complexity, synthesis, PPA estimation, quality score, testbench, and ML bug classifier in worker thread pool.
    """
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Empty Verilog code.")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False, encoding="utf-8") as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        # Run blocking EDA pipeline in worker threadpool so event loop is never blocked
        report = await run_in_threadpool(
            run_eda_analysis,
            tmp_path,
            use_llm=payload.use_llm,
            use_synth=payload.use_synth,
            use_tb=payload.use_tb,
        )
        res = report.to_dict()
        res["report_text"] = report.to_text()
        res["bug_probability"] = await run_in_threadpool(_compute_bug_prob, report)
        res["error"] = None
        return JSONResponse(content=res)
    except Exception as exc:
        print(f"[Error] Pipeline failure: {exc}")
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
async def compare_designs(payload: ComparisonPayload):
    """Compare two Verilog modules side by side."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False, encoding="utf-8") as tmp1:
        tmp1.write(payload.base_code)
        base_path = tmp1.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False, encoding="utf-8") as tmp2:
        tmp2.write(payload.target_code)
        target_path = tmp2.name

    try:
        base_rep = await run_in_threadpool(run_eda_analysis, base_path, False, True, False)
        target_rep = await run_in_threadpool(run_eda_analysis, target_path, False, True, False)
        return {
            "base": base_rep.to_dict(),
            "target": target_rep.to_dict()
        }
    finally:
        for p in [base_path, target_path]:
            try:
                os.unlink(p)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
