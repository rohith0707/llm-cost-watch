"""Zero-dependency execution tracer and logger wrapper for LLM calls.
Logs model, latency, tokens, and prompts to local json/sqlite storage.
"""

from __future__ import annotations

import functools
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

DATA_FILE = Path(__file__).resolve().parent / "data" / "llm_traces.json"

def log_trace(
    feature: str,
    model: str,
    prompt: str,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
    task_type: str = "general",
    status: str = "success"
) -> Dict[str, Any]:
    trace = {
        "id": f"tr_{uuid.uuid4().hex[:8]}",
        "feature": feature,
        "model": model,
        "task_type": task_type,
        "prompt": prompt[:500],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    traces = []
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                traces = json.load(f)
        except Exception:
            traces = []
            
    traces.append(trace)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(traces, f, indent=2)
        
    return trace

def watch_llm(feature: str, task_type: str = "general", model: str = "gpt-4o"):
    """Decorator to automatically time, measure tokens, and log any LLM function call."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            prompt_str = str(args[0]) if args else str(kwargs)
            try:
                res = func(*args, **kwargs)
                latency_ms = (time.perf_counter() - start) * 1000
                # Approximate tokens if not explicitly returned
                inp_tok = len(prompt_str) // 4
                out_tok = len(str(res)) // 4
                log_trace(feature, model, prompt_str, latency_ms, inp_tok, out_tok, task_type, "success")
                return res
            except Exception as e:
                latency_ms = (time.perf_counter() - start) * 1000
                log_trace(feature, model, prompt_str, latency_ms, len(prompt_str) // 4, 0, task_type, f"error: {str(e)[:50]}")
                raise e
        return wrapper
    return decorator
