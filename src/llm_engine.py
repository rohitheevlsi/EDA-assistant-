"""
LLM Engine - Phase 4
Uses Google Gemini to explain RTL modules and flag qualitative risks.
CONSTRAINT: Never state gate counts, area, or timing numbers. Pattern-based only.
"""

import os
from google import genai
from dotenv import load_dotenv


def _get_client():
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set. Add it to your .env file.")
    return genai.Client(api_key=api_key)


SYSTEM_PROMPT = """You are an expert RTL design reviewer embedded in an open-source EDA assistant.

You receive:
1. A structured IR summary of a Verilog module (module name, ports, internal signals, always-block count).
2. Static lint warnings already caught by a deterministic linter.

Your job:
A) Write a plain-English paragraph explaining what the module LIKELY does based purely on its
   port names, signal names, and structural patterns. Be specific and concise.
B) List any QUALITATIVE power or timing risk patterns you can infer from the structure.
   Examples of valid observations:
   - "This module has N always blocks driven combinationally — wide mux chains are possible."
   - "The presence of a latch (confirmed by lint) can cause hold-time issues in static timing analysis."
   - "The FIFO depth parameter controls memory footprint; large depths may stress area budgets."
   Rules:
   - DO NOT invent gate counts, MHz figures, ps delay, or area numbers.
   - DO NOT speculate beyond what the IR + lint results show.
   - Keep the tone technical but accessible to a junior designer.

Respond in Markdown with exactly two sections:
## Explanation
## Structural Risks
"""

MODELS = [
    "gemini-2.5-flash",        # primary — best quality on free tier
    "gemini-2.0-flash",        # fallback 1
    "gemini-2.0-flash-lite",   # fallback 2 — highest free quota
    "gemini-flash-latest",     # alias fallback — always resolves to latest flash
    "gemini-flash-lite-latest",# alias fallback lite — reliable last resort
]


import time

def _generate(client, prompt: str) -> tuple[str, str]:
    """Try each model in order until one succeeds. Returns (text, model_name)."""
    last_err = ""
    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                return response.text, model
            except Exception as e:
                last_err = str(e)
                if "429" in last_err or "RESOURCE_EXHAUSTED" in last_err:
                    time.sleep(3)  # Wait and retry
                    continue
                # If it's a 404 or other error, break out of retry loop to try next model
                break
    raise RuntimeError(f"All models exhausted. Last error: {last_err}")


def generate_explanation(module_name: str, ir_summary: dict, lint_results: list) -> str:
    """
    Generate a plain-English explanation and structural risk notes for a module.

    Args:
        module_name: Name of the Verilog module.
        ir_summary: Dict with keys: name, ports, signals, always_blocks.
        lint_results: List of lint warning strings from the static linter.

    Returns:
        Markdown string with Explanation and Structural Risks sections.
    """
    try:
        client = _get_client()
    except ValueError as e:
        return f"**LLM Error:** {e}"

    user_message = f"""
Module IR Summary:
  Name:          {ir_summary.get('name', module_name)}
  Ports:         {', '.join(ir_summary.get('ports', []))}
  Internal Signals: {', '.join(ir_summary.get('signals', [])) or '(none declared separately)'}
  Always Blocks: {ir_summary.get('always_blocks', 0)}

Static Lint Results:
{chr(10).join(f'  - {w}' for w in lint_results) if lint_results else '  - No issues found.'}
"""

    try:
        text, model = _generate(client, SYSTEM_PROMPT + "\n\n" + user_message)
        return text + f"\n\n*(Analysis generated using model: {model})*"
    except Exception as e:
        return f"**LLM Error:** {e}"


if __name__ == "__main__":
    # Quick smoke test
    test_ir = {
        "name": "multidriven_bug",
        "ports": ["clk", "a", "b", "out"],
        "signals": [],
        "always_blocks": 2,
    }
    test_lint = [
        "[MULTI-DRIVEN] Signal 'out' is driven in multiple always blocks (2 blocks) in module 'multidriven_bug'."
    ]
    print(generate_explanation("multidriven_bug", test_ir, test_lint))
