"""
Fetch and deduplicate open-source Verilog datasets:
1. MasterRTL (fangwenji/MasterRTL or hkust-zhiyao)
2. VerilogEval (NVlabs/verilog-eval)
3. RTLLM (hkust-zhiyao/RTLLM)

Stores deduplicated Verilog source files in data_generation/corpus/
"""

import os
import sys
import shutil
import hashlib
import subprocess
import glob
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
RAW_REPOS_DIR = BASE_DIR / "raw_repos"
CORPUS_DIR = BASE_DIR / "corpus"
EXISTING_TESTS_DIR = BASE_DIR.parent / "tests" / "verilog"

REPOS = {
    "verilog_eval": "https://github.com/NVlabs/verilog-eval.git",
    "rtllm": "https://github.com/hkust-zhiyao/RTLLM.git",
    "rtl_coder": "https://github.com/hkust-zhiyao/RTL-Coder.git",
    "assert_llm": "https://github.com/hkust-zhiyao/AssertLLM.git",
}


def compute_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of file content ignoring whitespace differences."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        cleaned = "".join(content.split())
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def clone_repo(name: str, url: str) -> Path:
    target = RAW_REPOS_DIR / name
    if target.exists():
        print(f"  [repo] {name} already exists at {target}")
        return target

    print(f"  [repo] Cloning {name} from {url}...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"  [repo] Successfully cloned {name}")
    except subprocess.CalledProcessError as e:
        print(f"  [repo] Git clone failed for {name}: {e.stderr}")
    return target


def main():
    RAW_REPOS_DIR.mkdir(parents=True, exist_ok=True)
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    seen_hashes = set()
    dedup_count = 0
    added_count = 0

    # 1. Index existing files in tests/verilog/
    print("[fetch] Indexing existing tests/verilog/ samples...")
    if EXISTING_TESTS_DIR.exists():
        for f in EXISTING_TESTS_DIR.glob("*.v"):
            h = compute_hash(f)
            if h:
                seen_hashes.add(h)
                # Also copy existing tests to corpus for unified training
                dest = CORPUS_DIR / f"test_{f.name}"
                shutil.copy2(f, dest)
                added_count += 1
    print(f"[fetch] Indexed {len(seen_hashes)} existing baseline designs.")

    # 2. Clone repos
    print("\n[fetch] Cloning dataset repositories...")
    for name, url in REPOS.items():
        clone_repo(name, url)

    # 3. Process each repo and extract .v files
    print("\n[fetch] Processing and deduplicating Verilog source files...")

    for repo_name in REPOS.keys():
        repo_dir = RAW_REPOS_DIR / repo_name
        if not repo_dir.exists():
            continue

        verilog_files = list(repo_dir.rglob("*.v")) + list(repo_dir.rglob("*.sv"))
        print(f"  [{repo_name}] Found {len(verilog_files)} HDL files")

        repo_added = 0
        repo_dedup = 0

        for vf in verilog_files:
            # Skip testbenches and tb files to keep pure design code
            fname_lower = vf.name.lower()
            if "tb" in fname_lower or "testbench" in fname_lower or "stimulus" in fname_lower:
                continue

            h = compute_hash(vf)
            if not h:
                continue

            if h in seen_hashes:
                dedup_count += 1
                repo_dedup += 1
                continue

            seen_hashes.add(h)

            # Generate clean filename
            clean_name = f"{repo_name}_{vf.parent.name}_{vf.name}".replace(" ", "_")
            dest = CORPUS_DIR / clean_name
            shutil.copy2(vf, dest)
            added_count += 1
            repo_added += 1

        print(f"  [{repo_name}] Added: {repo_added}, Duplicates/Testbenches skipped: {repo_dedup}")

    print("\n" + "=" * 60)
    print(f"[fetch] Dataset collection complete!")
    print(f"        Total unique designs in corpus: {added_count}")
    print(f"        Total duplicates/testbenches skipped: {dedup_count}")
    print(f"        Corpus directory: {CORPUS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
