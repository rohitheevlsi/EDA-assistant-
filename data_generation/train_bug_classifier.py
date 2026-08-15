"""
Train Bug/Anomaly Likelihood Classifier
Injects bug patterns programmatically into the training corpus,
extracts structural and rule-based features, and trains a RandomForestClassifier.
"""

import os
import re
import sys
import json
import pickle
import tempfile
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, precision_recall_fscore_support

# Add workspace directory to path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE_DIR)

from src.toolchain import setup_toolchain_env
os.environ.update(setup_toolchain_env())

from src.parser_ir import parse_verilog, summarize_ast
from src.linter import lint_ast
from src.synthesis import run_synthesis
from src.complexity import compute_complexity

# Define features used for training the classifier
FEATURE_NAMES = [
    "total_cells", "ff_cells", "logic_cells", "mux_cells", "buf_cells",
    "wires", "wire_bits", "register_bits", "clock_domains", "approx_cc",
    "nesting_depth", "port_count", "always_blocks",
    "warn_multi_driven", "warn_latch", "warn_cdc", "warn_blocking_seq",
    "warn_nonblocking_comb", "warn_undriven_port", "warn_unused_signal",
    "warn_no_default", "dlatch_cells"
]

def extract_ml_features(filepath):
    """Run full AST, complexity, and synthesis pipelines to extract classification features."""
    synth = run_synthesis(filepath)
    
    try:
        ast = parse_verilog(filepath)
        ir = summarize_ast(ast)
        ir_mod = ir["modules"][0] if ir["modules"] else {}
        cx = compute_complexity(ast, ir_mod)
        lints = lint_ast(ast)
    except Exception as e:
        cx = {}
        lints = ["Parser error"]

    warn_multi_driven = sum(1 for w in lints if "[MULTI-DRIVEN]" in w)
    warn_latch = sum(1 for w in lints if "[LATCH]" in w)
    warn_cdc = sum(1 for w in lints if "[CDC-CROSSING]" in w)
    warn_blocking_seq = sum(1 for w in lints if "[BLOCKING-IN-SEQ]" in w)
    warn_nonblocking_comb = sum(1 for w in lints if "[NONBLOCKING-IN-COMB]" in w)
    warn_undriven_port = sum(1 for w in lints if "[UNDRIVEN-PORT]" in w)
    warn_unused_signal = sum(1 for w in lints if "[UNUSED-SIGNAL]" in w)
    warn_no_default = sum(1 for w in lints if "[NO-DEFAULT-CASE]" in w)

    gates = synth.gates or {}
    total = synth.total_cells or 0
    ff = sum(n for c, n in gates.items() if "DFF" in c or "DLATCH" in c or "SDFF" in c)
    mux = sum(n for c, n in gates.items() if "MUX" in c)
    buf = sum(n for c, n in gates.items() if "BUF" in c or "NOT" in c)
    logic = max(0, total - ff - mux - buf)
    dlatch_cells = gates.get("$_DLATCH_P_", 0) + gates.get("$_DLATCH_N_", 0)

    return {
        "total_cells": total,
        "ff_cells": ff,
        "logic_cells": logic,
        "mux_cells": mux,
        "buf_cells": buf,
        "wires": synth.wires,
        "wire_bits": synth.wire_bits,
        "register_bits": cx.get("register_bits", 0),
        "clock_domains": cx.get("clock_domain_count", 0),
        "approx_cc": cx.get("approximated_cyclomatic_complexity", 1),
        "nesting_depth": cx.get("max_nesting_depth", 0),
        "port_count": cx.get("port_count", 0),
        "always_blocks": cx.get("always_blocks", 0),
        "warn_multi_driven": warn_multi_driven,
        "warn_latch": warn_latch,
        "warn_cdc": warn_cdc,
        "warn_blocking_seq": warn_blocking_seq,
        "warn_nonblocking_comb": warn_nonblocking_comb,
        "warn_undriven_port": warn_undriven_port,
        "warn_unused_signal": warn_unused_signal,
        "warn_no_default": warn_no_default,
        "dlatch_cells": dlatch_cells
    }

def inject_bugs(code):
    """Mutate code to programmatically inject a variety of common buggy Verilog patterns."""
    mutations = []
    
    # Bug Pattern 1: Swap assignments
    if "<=" in code:
        mutations.append(code.replace("<=", "="))
    
    # Bug Pattern 2: Drop else branch
    if "else" in code:
        mutations.append(re.sub(r'\belse\b\s*(?:begin\b[\s\S]*?\bend\b|[^;]*;)', '', code))
        
    # Bug Pattern 3: Drop case default
    if "default" in code:
        mutations.append(re.sub(r'\bdefault\s*:\s*.*', '', code))

    # Bug Pattern 4: Swap blocking to non-blocking in comb
    if "=" in code and "<=" not in code:
        mutations.append(code.replace("=", "<="))

    return mutations

def main():
    csv_path = os.path.join(WORKSPACE_DIR, "data_generation", "synthesis_dataset.csv")
    if not os.path.exists(csv_path):
        print(f"Error: dataset CSV not found at {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    sources = df["source"].dropna().unique()
    # Limit to 50 representative samples for fast training run
    MAX_SAMPLES = 15
    if len(sources) > MAX_SAMPLES:
        np.random.seed(42)
        sources = np.random.choice(sources, size=MAX_SAMPLES, replace=False)
    
    print(f"Starting Bug Classifier training pipeline. Using {len(sources)} designs from training CSV.")
    
    dataset = []
    
    for idx, filename in enumerate(sources):
        filepath = os.path.join(WORKSPACE_DIR, "data_generation", "corpus", filename)
        if not os.path.exists(filepath):
            continue
            
        print(f"[{idx+1}/{len(sources)}] Processing clean: {filename}")
        
        # 1. Clean sample
        try:
            clean_feats = extract_ml_features(filepath)
            clean_feats["is_buggy"] = 0
            dataset.append(clean_feats)
        except Exception as e:
            print(f"  Failed to extract clean features: {e}")
            continue

        # 2. Buggy mutations
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
            
        mutated_versions = inject_bugs(code)
        for m_idx, mut_code in enumerate(mutated_versions[:2]):  # limit to 2 mutations per file to balance classes
            with tempfile.NamedTemporaryFile(suffix=".v", delete=False, mode="w", encoding="utf-8") as tmp:
                tmp.write(mut_code)
                tmp_path = tmp.name
                
            try:
                mut_feats = extract_ml_features(tmp_path)
                mut_feats["is_buggy"] = 1
                dataset.append(mut_feats)
            except Exception as e:
                pass
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass

    dataset_df = pd.DataFrame(dataset)
    print(f"\nDataset construction complete. Shape: {dataset_df.shape}")
    print(f"Class counts:\n{dataset_df['is_buggy'].value_counts()}")
    
    X = dataset_df[FEATURE_NAMES]
    y = dataset_df["is_buggy"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print("Training RandomForestClassifier...")
    clf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=8)
    clf.fit(X_train, y_train)
    
    # Evaluate
    y_pred = clf.predict(X_test)
    print("\nEvaluation Report on 20% Test Split:")
    print(classification_report(y_test, y_pred))
    
    # Get precision/recall/f1 metrics to save metadata
    prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="binary")
    
    # Feature importances
    importances = clf.feature_importances_
    feat_imp = sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
    print("Feature Importances:")
    for feat, imp in feat_imp[:10]:
        print(f"  {feat}: {imp:.4f}")
        
    # Save Model
    model_dir = os.path.join(WORKSPACE_DIR, "models")
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, "bug_classifier.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)
    print(f"\nSaved model to {model_path}")
    
    meta_path = os.path.join(model_dir, "bug_classifier_meta.json")
    meta = {
        "num_samples": len(dataset_df),
        "precision": float(prec),
        "recall": float(rec),
        "f1_score": float(f1),
        "feature_importances": {feat: float(imp) for feat, imp in feat_imp}
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved metadata to {meta_path}")

if __name__ == "__main__":
    main()
